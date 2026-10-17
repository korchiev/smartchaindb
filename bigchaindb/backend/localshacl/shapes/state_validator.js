import { tracked, expired, withStateContext } from './state_context.js';
const dlog = (...args) => { if (process.env.SHACL_DEBUG === '1') console.log(...args); };

async function metadataFor(txId) {
    const row = await tracked('metadata').findOne({ id: txId });
    return row && row.metadata ? row.metadata : null;
}

function createOwnerKeys(createTx) {
    if (!createTx || !Array.isArray(createTx.outputs) || !createTx.outputs[0]) {
        return [];
    }
    const keys = createTx.outputs[0].public_keys;
    return Array.isArray(keys) ? keys : [];
}

/**
 * Original ADVERTISEMENT metadata stays OPEN. Later UPDATE_ADV txs
 * carry the current status (same overlay Fabric applies in world state).
 */
async function latestAdvertisementStatus(advertisementId, transactions) {
    const orig = await metadataFor(advertisementId);
    let status = orig && orig.status;
    const updates = await transactions.find({
        operation: 'UPDATE_ADV',
        $or: [
            { 'asset.id': advertisementId },
            { 'asset.data.id': advertisementId }
        ]
    }).sort({ _id: 1 }).toArray();
    for (const upd of updates) {
        const meta = await metadataFor(upd.id);
        if (meta && meta.status) {
            status = meta.status;
        }
    }
    return status;
}

/**
 * Validate state consistency using MongoDB queries
 */
async function validateStateConsistency(txData) {
    const errors = [];



    const transactions = tracked('transactions');

    try {
        switch (txData.operation) {
            case 'ADVERTISEMENT':
                await validateAdvertisement(txData, transactions, errors);
                break;
            case 'UPDATE_ADV':
                await validateUpdateAdv(txData, transactions, errors);
                break;

            case 'BUY_OFFER':
                await validateBuyOffer(txData, transactions, errors);
                break;

            case 'SELL':
                await validateSell(txData, transactions, errors);
                break;

            case 'TRANSFER':
                await validateTransfer(txData, transactions, errors);
                break;

            case 'REQUEST_RETURN':
                await validateRequestReturn(txData, transactions, errors);
                break;

            case 'SELLER_ACCEPT_RETURN':
                await validateSellerAcceptReturn(txData, transactions, errors);
                break;
        }
    } catch (error) {
        // Unavailable/incomplete state is not a semantic rejection and must
        // never be inserted into the verdict cache.
        throw error;
    }

    return errors;
}

/**
 * Validate UPDATE_ADV transaction state
 */
async function validateUpdateAdv(txData, transactions, errors) {
    dlog('Validating UPDATE_ADV transaction:', txData.id);
    const advertisementId = txData.asset.data.id;
    if (!advertisementId) {
        dlog('ERROR: asset.data.id is missing');
        errors.push({
            message: ['asset.data.id is required for UPDATE_ADV'],
            path: 'http://bigchaindb.com/ns#id',
            focusNode: `urn:tx:${txData.id}`,
            severity: 'Violation'
        });
        return;
    }

    const adv = await transactions.findOne({ id: advertisementId, operation: 'ADVERTISEMENT' });
    if (!adv) {
        dlog('ERROR: Advertisement not found:', advertisementId);
        errors.push({
            message: [`Advertisement '${advertisementId}' does not exist`],
            path: 'http://bigchaindb.com/ns#id',
            focusNode: `urn:tx:${txData.id}`,
            severity: 'Violation'
        });
        return;
    }

    // Owner check: updater must match advertiser
    const advMeta = await tracked('metadata').findOne({ id: advertisementId });
    const advertiser = advMeta && advMeta.metadata && (advMeta.metadata.advertiser_public_key || advMeta.metadata.seller_public_key);
    const inputOwner = (txData.inputs && txData.inputs[0] && txData.inputs[0].owners_before && txData.inputs[0].owners_before[0]) || null;
    dlog('Advertisement metadata:', advMeta);
    dlog('Advertiser:', advertiser);
    dlog('Input owner:', inputOwner);
    if (!inputOwner || !advertiser || inputOwner !== advertiser) {
        dlog('ERROR: Owner mismatch');
        errors.push({
            message: ['Only the advertiser can update the advertisement'],
            path: 'http://bigchaindb.com/ns#updater_public_key',
            focusNode: `urn:tx:${txData.id}`,
            severity: 'Violation'
        });
    }

    // Status transition check
    const currentStatus = await latestAdvertisementStatus(advertisementId, transactions);
    const nextStatus = txData.metadata.status;
    const allowed = { OPEN: ['LOCKED', 'CLOSED'], LOCKED: ['CLOSED'], CLOSED: [] };
    if (nextStatus && currentStatus && !allowed[currentStatus]?.includes(nextStatus) && nextStatus !== currentStatus) {
        errors.push({
            message: [`Invalid status transition ${currentStatus} -> ${nextStatus}`],
            path: 'http://bigchaindb.com/ns#status',
            focusNode: `urn:tx:${txData.id}`,
            severity: 'Violation'
        });
    }

    // Expiry check
    if ((txData.metadata.expiry_date || txData.metadata.expiry) && expired(txData.metadata.expiry_date || txData.metadata.expiry)) {
        errors.push({
            message: ['expiry must be in the future'],
            path: 'http://bigchaindb.com/ns#expiry',
            focusNode: `urn:tx:${txData.id}`,
            severity: 'Violation'
        });
    }
}
async function validateAdvertisement(txData, transactions, errors) {
    // Check if asset exists (if asset.id is provided)
    const assetId = txData.asset.id || (txData.asset.data && txData.asset.data.id);

    if (assetId) {
        const asset = await transactions.findOne({
            id: assetId,
            operation: 'CREATE'
        });

        if (!asset) {
            errors.push({
                message: [`Asset with id '${assetId}' does not exist`],
                path: 'http://bigchaindb.com/ns#asset',
                focusNode: `urn:tx:${txData.id}`,
                severity: 'Violation'
            });
        } else {
            const advertiser = txData.metadata && txData.metadata.advertiser_public_key;
            const owners = createOwnerKeys(asset);
            if (!advertiser || owners.length === 0 || owners.indexOf(advertiser) === -1) {
                errors.push({
                    message: ['Advertiser must be the original owner of the asset'],
                    path: 'http://bigchaindb.com/ns#advertiser_public_key',
                    focusNode: `urn:tx:${txData.id}`,
                    severity: 'Violation'
                });
            }
        }

        // Metadata is stored separately; evaluate effective status rather
        // than querying an absent transactions.metadata.status property.
        const advertisements = await transactions.find({
            operation: 'ADVERTISEMENT', 'asset.id': assetId
        }).toArray();
        for (const existingAd of advertisements) {
            if (existingAd.id === txData.id) continue;
            const status = await latestAdvertisementStatus(existingAd.id, transactions);
            if (status === 'OPEN' || status === 'LOCKED') {
                errors.push({message: ['Asset already has an active advertisement'],
                    path: 'http://bigchaindb.com/ns#asset',
                    focusNode: `urn:tx:${txData.id}`, severity: 'Violation'});
                break;
            }
        }
    }
}

/**
 * Validate BUY_OFFER transaction state
 */
async function validateBuyOffer(txData, transactions, errors) {
    const advertisementId = txData.asset.data.advertisement_id;

    if (!advertisementId) {
        errors.push({
            message: ['advertisement_id is required in asset data'],
            path: 'http://bigchaindb.com/ns#advertisement_id',
            focusNode: `urn:tx:${txData.id}`,
            severity: 'Violation'
        });
        return;
    }

    // Check if advertisement exists
    const advertisement = await transactions.findOne({
        id: advertisementId,
        operation: 'ADVERTISEMENT'
    });

    if (!advertisement) {
        errors.push({
            message: [`Advertisement with id '${advertisementId}' does not exist`],
            path: 'http://bigchaindb.com/ns#advertisement_id',
            focusNode: `urn:tx:${txData.id}`,
            severity: 'Violation'
        });
        return;
    }

    const adAssetId = advertisement.asset && advertisement.asset.id;
    // The asset id arrives as bdb:id on the asset blank node, which the RDF
    // extraction stores under asset.data.id.
    const offerAssetId = txData.asset && (txData.asset.id || (txData.asset.data && txData.asset.data.id));
    if (adAssetId && offerAssetId && offerAssetId !== adAssetId) {
        errors.push({
            message: [`Buy offer asset does not match the advertisement's asset`],
            path: 'http://bigchaindb.com/ns#advertisement_id',
            focusNode: `urn:tx:${txData.id}`,
            severity: 'Violation'
        });
    }

    const status = await latestAdvertisementStatus(advertisementId, transactions);
    if (status !== 'OPEN') {
        errors.push({
            message: [`Advertisement '${advertisementId}' is not open for offers (status: ${status || 'unknown'})`],
            path: 'http://bigchaindb.com/ns#advertisement_id',
            focusNode: `urn:tx:${txData.id}`,
            severity: 'Violation'
        });
    }

    const adMeta = await metadataFor(advertisementId);
    const advertiser = adMeta && adMeta.advertiser_public_key;
    const buyer = txData.metadata && txData.metadata.buyer_public_key;
    if (buyer && advertiser && buyer === advertiser) {
        errors.push({
            message: ['Buyer cannot be the same as advertiser'],
            path: 'http://bigchaindb.com/ns#buyer_public_key',
            focusNode: `urn:tx:${txData.id}`,
            severity: 'Violation'
        });
    }

    // Check if offer has expired
    const offerExpiry = txData.metadata.offer_expiry;
    if (offerExpiry && expired(offerExpiry)) {
        errors.push({
            message: [`Offer has already expired at ${offerExpiry}`],
            path: 'http://bigchaindb.com/ns#offer_expiry',
            focusNode: `urn:tx:${txData.id}`,
            severity: 'Violation'
        });
    }

    // Check if payment_asset_id exists (if provided)
    const paymentAssetId = txData.metadata.payment_asset_id;
    if (paymentAssetId) {
        const paymentAsset = await transactions.findOne({
            id: paymentAssetId
        });

        if (!paymentAsset) {
            errors.push({
                message: [`Payment asset '${paymentAssetId}' does not exist`],
                path: 'http://bigchaindb.com/ns#payment_asset_id',
                focusNode: `urn:tx:${txData.id}`,
                severity: 'Violation'
            });
        }
    }
}

/**
 * Validate SELL transaction state
 */
async function validateSell(txData, transactions, errors) {
    dlog('Validating SELL transaction:', txData.id);
    const buyOfferId = txData.asset.data.buy_offer_id;

    if (!buyOfferId) {
        dlog('ERROR: buy_offer_id is missing');
        errors.push({
            message: ['buy_offer_id is required in asset data'],
            path: 'http://bigchaindb.com/ns#buy_offer_id',
            focusNode: `urn:tx:${txData.id}`,
            severity: 'Violation'
        });
        return;
    }

    // Check if buy offer exists
    const buyOffer = await transactions.findOne({
        id: buyOfferId,
        operation: 'BUY_OFFER'
    });

    if (!buyOffer) {
        dlog('ERROR: Buy offer not found:', buyOfferId);
        errors.push({
            message: [`Buy offer with id '${buyOfferId}' does not exist`],
            path: 'http://bigchaindb.com/ns#buy_offer_id',
            focusNode: `urn:tx:${txData.id}`,
            severity: 'Violation'
        });
        return;
    }

    dlog('Buy offer found:', buyOffer.id);

    // Get buy offer metadata from separate collection
    const buyOfferMetadata = await tracked('metadata').findOne({
        id: buyOfferId
    });

    if (!buyOfferMetadata || !buyOfferMetadata.metadata) {
        errors.push({
            message: [`Buy offer '${buyOfferId}' has no metadata`],
            path: 'http://bigchaindb.com/ns#buy_offer_id',
            focusNode: `urn:tx:${txData.id}`,
            severity: 'Violation'
        });
        return;
    }

    // Check if buy offer has expired
    const offerExpiry = buyOfferMetadata.metadata.offer_expiry;
    if (offerExpiry && expired(offerExpiry)) {
        errors.push({
            message: [`Buy offer '${buyOfferId}' has expired at ${offerExpiry}`],
            path: 'http://bigchaindb.com/ns#buy_offer_id',
            focusNode: `urn:tx:${txData.id}`,
            severity: 'Violation'
        });
    }

    // Verify sale amount matches offer amount
    const saleAmount = txData.metadata.sale_amount;
    const offerAmount = buyOfferMetadata.metadata.offer_amount;

    if (saleAmount !== offerAmount) {
        errors.push({
            message: [`Sale amount (${saleAmount}) does not match buy offer amount (${offerAmount})`],
            path: 'http://bigchaindb.com/ns#sale_amount',
            focusNode: `urn:tx:${txData.id}`,
            severity: 'Violation'
        });
    }

    // Check if asset has already been sold
    const existingSale = await transactions.findOne({
        operation: 'SELL',
        'asset.data.buy_offer_id': buyOfferId
    });

    if (existingSale && existingSale.id !== txData.id) {
        errors.push({
            message: [`Buy offer '${buyOfferId}' has already been accepted by another SELL transaction`],
            path: 'http://bigchaindb.com/ns#buy_offer_id',
            focusNode: `urn:tx:${txData.id}`,
            severity: 'Violation'
        });
    }

    const offerAsset = buyOffer.asset || {};
    const offerData = offerAsset.data || {};
    const advertisementId = offerAsset.advertisement_id || offerData.advertisement_id;
    if (advertisementId) {
        const adMetaForSell = await metadataFor(advertisementId);
        const seller = txData.metadata && txData.metadata.seller_public_key;
        const advertiser = adMetaForSell && adMetaForSell.advertiser_public_key;
        if (seller && advertiser && seller !== advertiser) {
            errors.push({
                message: ['Seller must be the advertiser (current owner) of the asset'],
                path: 'http://bigchaindb.com/ns#seller_public_key',
                focusNode: `urn:tx:${txData.id}`,
                severity: 'Violation'
            });
        }
        const adStatus = await latestAdvertisementStatus(advertisementId, transactions);
        if (adStatus === 'LOCKED' || adStatus === 'CLOSED') {
            errors.push({
                message: [`Cannot sell asset with advertisement status ${adStatus}`],
                path: 'http://bigchaindb.com/ns#buy_offer_id',
                focusNode: `urn:tx:${txData.id}`,
                severity: 'Violation'
            });
        }
    }
}

/**
 * Validate TRANSFER transaction state
 */
async function validateTransfer(txData, transactions, errors) {
    // Check if asset being transferred exists
    const assetId = txData.asset.id;

    if (assetId) {
        const asset = await transactions.findOne({
            id: assetId
        });

        if (!asset) {
            errors.push({
                message: [`Asset with id '${assetId}' does not exist`],
                path: 'http://bigchaindb.com/ns#asset',
                focusNode: `urn:tx:${txData.id}`,
                severity: 'Violation'
            });
        }
    }
}

/**
 * Validate REQUEST_RETURN transaction state
 */
async function validateRequestReturn(txData, transactions, errors) {
    dlog('Validating REQUEST_RETURN transaction:', txData.id);
    const sellTransactionId = txData.asset.data.sell_transaction_id;

    if (!sellTransactionId) {
        dlog('ERROR: sell_transaction_id is missing');
        errors.push({
            message: ['sell_transaction_id is required in asset'],
            path: 'http://bigchaindb.com/ns#sell_transaction_id',
            focusNode: `urn:tx:${txData.id}`,
            severity: 'Violation'
        });
        return;
    }

    // Check if sell transaction exists
    const sellTransaction = await transactions.findOne({
        id: sellTransactionId,
        operation: 'SELL'
    });

    if (!sellTransaction) {
        dlog('ERROR: Sell transaction not found:', sellTransactionId);
        errors.push({
            message: [`Sell transaction with id '${sellTransactionId}' does not exist`],
            path: 'http://bigchaindb.com/ns#sell_transaction_id',
            focusNode: `urn:tx:${txData.id}`,
            severity: 'Violation'
        });
        return;
    }

    dlog('Sell transaction found:', sellTransaction.id);

    // Get sell transaction metadata
    const sellMetadata = await tracked('metadata').findOne({
        id: sellTransactionId
    });

    if (!sellMetadata || !sellMetadata.metadata) {
        dlog('ERROR: Sell transaction metadata not found for:', sellTransactionId);
        errors.push({
            message: [`Sell transaction '${sellTransactionId}' has no metadata`],
            path: 'http://bigchaindb.com/ns#sell_transaction_id',
            focusNode: `urn:tx:${txData.id}`,
            severity: 'Violation'
        });
        return;
    }

    const requester = txData.metadata && txData.metadata.requester_public_key;
    const buyer = sellMetadata.metadata.buyer_public_key;
    if (requester && buyer && requester !== buyer) {
        errors.push({
            message: ['Requester must be the buyer of the sale'],
            path: 'http://bigchaindb.com/ns#requester_public_key',
            focusNode: `urn:tx:${txData.id}`,
            severity: 'Violation'
        });
    }

    // Check if return is within the return window
    const returnRequestTimestamp = txData.metadata.return_request_timestamp;
    const saleTimestamp = sellMetadata.metadata.sale_timestamp;
    const returnWindowDays = txData.metadata.return_policy_details?.return_window_days || 30;

    if (returnRequestTimestamp && saleTimestamp) {
        const requestDate = new Date(returnRequestTimestamp);
        const saleDate = new Date(saleTimestamp);
        const daysDiff = (requestDate - saleDate) / (1000 * 60 * 60 * 24);

        dlog('Return request days after sale:', daysDiff, 'Window:', returnWindowDays);

        if (daysDiff > returnWindowDays) {
            dlog('ERROR: Return request exceeds return window');
            errors.push({
                message: [`Return request is ${daysDiff.toFixed(1)} days after sale, exceeds ${returnWindowDays} day window`],
                path: 'http://bigchaindb.com/ns#return_request_timestamp',
                focusNode: `urn:tx:${txData.id}`,
                severity: 'Violation'
            });
        }
    }

    // Check if a return request already exists for this sell transaction
    const existingReturnRequest = await transactions.findOne({
        operation: 'REQUEST_RETURN',
        'asset.data.sell_transaction_id': sellTransactionId
    });

    if (existingReturnRequest && existingReturnRequest.id !== txData.id) {
        dlog('ERROR: Return request already exists for sell transaction:', sellTransactionId);
        errors.push({
            message: [`A return request already exists for sell transaction '${sellTransactionId}'`],
            path: 'http://bigchaindb.com/ns#sell_transaction_id',
            focusNode: `urn:tx:${txData.id}`,
            severity: 'Violation'
        });
    }
}

/**
 * Validate SELLER_ACCEPT_RETURN transaction state
 */
async function validateSellerAcceptReturn(txData, transactions, errors) {
    dlog('Validating SELLER_ACCEPT_RETURN transaction:', txData.id);
    const requestReturnId = txData.asset.data.request_return_id;

    if (!requestReturnId) {
        dlog('ERROR: request_return_id is missing');
        errors.push({
            message: ['request_return_id is required in asset'],
            path: 'http://bigchaindb.com/ns#request_return_id',
            focusNode: `urn:tx:${txData.id}`,
            severity: 'Violation'
        });
        return;
    }

    // Check if REQUEST_RETURN transaction exists
    const requestReturnTransaction = await transactions.findOne({
        id: requestReturnId,
        operation: 'REQUEST_RETURN'
    });

    if (!requestReturnTransaction) {
        dlog('ERROR: REQUEST_RETURN transaction not found:', requestReturnId);
        errors.push({
            message: [`REQUEST_RETURN transaction with id '${requestReturnId}' does not exist`],
            path: 'http://bigchaindb.com/ns#request_return_id',
            focusNode: `urn:tx:${txData.id}`,
            severity: 'Violation'
        });
        return;
    }

    dlog('REQUEST_RETURN transaction found:', requestReturnTransaction.id);

    // Get REQUEST_RETURN metadata
    const requestReturnMetadata = await tracked('metadata').findOne({
        id: requestReturnId
    });

    if (!requestReturnMetadata || !requestReturnMetadata.metadata) {
        dlog('ERROR: REQUEST_RETURN metadata not found for:', requestReturnId);
        errors.push({
            message: [`REQUEST_RETURN transaction '${requestReturnId}' has no metadata`],
            path: 'http://bigchaindb.com/ns#request_return_id',
            focusNode: `urn:tx:${txData.id}`,
            severity: 'Violation'
        });
        return;
    }

    const returnAsset = requestReturnTransaction.asset || {};
    const returnData = returnAsset.data || {};
    const acceptedSellId = returnData.sell_transaction_id || returnAsset.sell_transaction_id;
    if (acceptedSellId) {
        const acceptedSellMeta = await tracked('metadata').findOne({ id: acceptedSellId });
        const acceptor = txData.metadata && txData.metadata.seller_public_key;
        const saleSeller = acceptedSellMeta && acceptedSellMeta.metadata && acceptedSellMeta.metadata.seller_public_key;
        if (acceptor && saleSeller && acceptor !== saleSeller) {
            errors.push({
                message: ['Only the seller of the sale can accept the return'],
                path: 'http://bigchaindb.com/ns#seller_public_key',
                focusNode: `urn:tx:${txData.id}`,
                severity: 'Violation'
            });
        }
    }

    // Check if a SELLER_ACCEPT_RETURN already exists for this REQUEST_RETURN
    const existingSellerAcceptReturn = await transactions.findOne({
        operation: 'SELLER_ACCEPT_RETURN',
        'asset.data.request_return_id': requestReturnId
    });

    if (existingSellerAcceptReturn && existingSellerAcceptReturn.id !== txData.id) {
        dlog('ERROR: SELLER_ACCEPT_RETURN already exists for REQUEST_RETURN:', requestReturnId);
        errors.push({
            message: [`A SELLER_ACCEPT_RETURN already exists for REQUEST_RETURN '${requestReturnId}'`],
            path: 'http://bigchaindb.com/ns#request_return_id',
            focusNode: `urn:tx:${txData.id}`,
            severity: 'Violation'
        });
    }
}

/**
 * Evaluate the rules in an isolated request context with the accepted prefix.
 */

export async function validateState(txData, options) {
  return withStateContext(options, () => validateStateConsistency(txData));
}

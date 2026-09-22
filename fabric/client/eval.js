import { Gateway, Wallets } from 'fabric-network';
import fs from 'fs';

const fn = process.argv[2];
const arg = process.argv[3];

async function main() {
  const ccp = JSON.parse(fs.readFileSync(process.env.FABRIC_CONNECTION_PROFILE, 'utf8'));
  const wallet = await Wallets.newFileSystemWallet(process.env.FABRIC_WALLET_DIR);
  const gateway = new Gateway();
  await gateway.connect(ccp, {
    wallet,
    identity: process.env.FABRIC_IDENTITY || 'appUser',
    discovery: { enabled: true, asLocalhost: true },
  });
  const network = await gateway.getNetwork(process.env.FABRIC_CHANNEL || 'mychannel');
  const contract = network.getContract(process.env.FABRIC_CONTRACT || 'marketplace');
  try {
    const buf = await contract.evaluateTransaction(fn, arg);
    console.log('RESULT:', buf.toString());
  } catch (e) {
    console.error('EVAL_ERROR:', e.message || e);
  } finally {
    gateway.disconnect();
  }
}

main()
  .then(() => process.exit(0))
  .catch((e) => {
    console.error(e);
    process.exit(1);
  });

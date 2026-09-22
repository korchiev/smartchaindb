import FabricCAServices from 'fabric-ca-client';
import { Wallets } from 'fabric-network';
import fs from 'fs';
import path from 'path';
import os from 'os';

function caInfoFromCcp(ccp) {
  const cas = ccp.certificateAuthorities || {};
  const name = Object.keys(cas)[0];
  if (!name) return null;
  return { name, ...cas[name] };
}

function tlsPem(caInfo) {
  if (caInfo.tlsCACerts?.pem) return caInfo.tlsCACerts.pem;
  if (caInfo.tlsCACerts?.path) return fs.readFileSync(caInfo.tlsCACerts.path, 'utf8');
  throw new Error('CA TLS cert missing from connection profile');
}

async function importCryptogenIdentity(wallet, userId, mspId) {
  const mspDir =
    process.env.FABRIC_USER_MSP ||
    path.join(
      os.homedir(),
      'fabric-samples/test-network/organizations/peerOrganizations/org1.example.com/users/User1@org1.example.com/msp',
    );
  const certDir = path.join(mspDir, 'signcerts');
  const keyDir = path.join(mspDir, 'keystore');
  const certFile = fs.readdirSync(certDir).find((f) => f.endsWith('.pem'));
  const keyFile = fs.readdirSync(keyDir)[0];
  if (!certFile || !keyFile) {
    throw new Error(`Could not find cert/key under ${mspDir}`);
  }
  await wallet.put(userId, {
    credentials: {
      certificate: fs.readFileSync(path.join(certDir, certFile), 'utf8'),
      privateKey: fs.readFileSync(path.join(keyDir, keyFile), 'utf8'),
    },
    mspId,
    type: 'X.509',
  });
  console.log(`Imported cryptogen identity ${userId} from ${mspDir}`);
}

async function enrollWithCa(ccp, wallet, userId, mspId) {
  const caInfo = caInfoFromCcp(ccp);
  if (!caInfo) throw new Error('No certificateAuthorities in connection profile');
  const ca = new FabricCAServices(
    caInfo.url,
    { trustedRoots: tlsPem(caInfo), verify: false },
    caInfo.caName || caInfo.name,
  );

  if (!(await wallet.get('admin'))) {
    const enrollment = await ca.enroll({ enrollmentID: 'admin', enrollmentSecret: 'adminpw' });
    await wallet.put('admin', {
      credentials: { certificate: enrollment.certificate, privateKey: enrollment.key.toBytes() },
      mspId,
      type: 'X.509',
    });
    console.log('Enrolled admin');
  } else {
    console.log('Admin already in wallet');
  }

  if (await wallet.get(userId)) {
    console.log(`${userId} already in wallet`);
    return;
  }

  const adminIdentity = await wallet.get('admin');
  const provider = wallet.getProviderRegistry().getProvider(adminIdentity.type);
  const adminUser = await provider.getUserContext(adminIdentity, 'admin');
  const secret = await ca.register(
    { affiliation: 'org1.department1', enrollmentID: userId, role: 'client', maxEnrollments: -1 },
    adminUser,
  );
  const enrollment = await ca.enroll({ enrollmentID: userId, enrollmentSecret: secret });
  await wallet.put(userId, {
    credentials: { certificate: enrollment.certificate, privateKey: enrollment.key.toBytes() },
    mspId,
    type: 'X.509',
  });
  console.log(`Enrolled ${userId}`);
}

async function main() {
  const ccpPath = process.env.FABRIC_CONNECTION_PROFILE;
  const walletDir = process.env.FABRIC_WALLET_DIR;
  const userId = process.env.FABRIC_IDENTITY || 'appUser';
  const mspId = process.env.FABRIC_MSPID || 'Org1MSP';
  if (!ccpPath || !walletDir) {
    throw new Error('Set FABRIC_CONNECTION_PROFILE and FABRIC_WALLET_DIR');
  }

  const ccp = JSON.parse(fs.readFileSync(ccpPath, 'utf8'));
  fs.mkdirSync(walletDir, { recursive: true });
  const wallet = await Wallets.newFileSystemWallet(walletDir);

  if (await wallet.get(userId)) {
    console.log(`${userId} already in wallet ${path.resolve(walletDir)}`);
    return;
  }

  try {
    await enrollWithCa(ccp, wallet, userId, mspId);
  } catch (err) {
    const msg = err && err.message ? err.message : String(err);
    if (!/ECONNREFUSED|ENOTFOUND|certificateAuthorities/.test(msg) && err.code !== 'ECONNREFUSED') {
      throw err;
    }
    console.log(`Fabric CA unavailable (${msg}); importing cryptogen User1 identity instead`);
    await importCryptogenIdentity(wallet, userId, mspId);
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
}).then(() => process.exit(0));

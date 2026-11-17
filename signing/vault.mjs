// Runs only on the disposable GitHub-hosted runner. Never print signing secrets.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {spawnSync} from 'node:child_process';
if(process.env.GITHUB_ACTIONS!=='true'||process.env.RUNNER_ENVIRONMENT!=='github-hosted')
  throw new Error('Signing is cloud-only');
const pass=process.env.FEISHU_SIGNING_PASSWORD||'';
if(pass.length<43) throw new Error('A separately saved high-entropy signing password is required');
const root=process.cwd();
const vaultPath=path.join(root,'signing','release-key.enc.json');
const work=path.join(process.env.RUNNER_TEMP,'feishu-signing');
fs.mkdirSync(work,{recursive:true,mode:0o700});
const keyFile=path.join(work,'release.p12');
const certFile=path.join(work,'certificate.der');
function run(args) {
  const p=spawnSync('keytool',args,{encoding:'utf8'});
  if(p.status!==0) throw new Error('keytool failed: '+String(p.stderr).replaceAll(pass,'[redacted]'));
  return p.stdout;
}
const alias='feishu-wake-release';
const aad=Buffer.from('FeishuWake:dev.feishuwake:release-key:v1');
const mode=process.argv[2];
if(mode==='init') {
  if(fs.existsSync(vaultPath)) throw new Error('Fixed signing key already exists; refusing replacement');
  run(['-genkeypair','-keystore',keyFile,'-storetype','PKCS12','-alias',alias,
    '-keyalg','RSA','-keysize','3072','-sigalg','SHA256withRSA','-validity','10000',
    '-dname','CN=Feishu Wake Release, O=Feishu Wake',
    '-storepass:env','FEISHU_SIGNING_PASSWORD','-keypass:env','FEISHU_SIGNING_PASSWORD','-noprompt']);
  run(['-exportcert','-keystore',keyFile,'-alias',alias,'-storepass:env','FEISHU_SIGNING_PASSWORD','-file',certFile]);
  const cert=fs.readFileSync(certFile);
  const certificateSha256=crypto.createHash('sha256').update(cert).digest('hex');
  const salt=crypto.randomBytes(32), nonce=crypto.randomBytes(12);
  const key=crypto.pbkdf2Sync(pass,salt,600000,32,'sha256');
  const cipher=crypto.createCipheriv('aes-256-gcm',key,nonce);
  cipher.setAAD(aad);
  const ciphertext=Buffer.concat([cipher.update(fs.readFileSync(keyFile)),cipher.final()]);
  const envelope={format:'feishu-signing-v1',package:'dev.feishuwake',alias,
    certificate_sha256:certificateSha256,kdf:'PBKDF2-HMAC-SHA256',iterations:600000,
    cipher:'AES-256-GCM',salt:salt.toString('base64'),nonce:nonce.toString('base64'),
    tag:cipher.getAuthTag().toString('base64'),ciphertext:ciphertext.toString('base64')};
  const dest=path.join(root,'reports','signing-init');
  fs.mkdirSync(dest,{recursive:true});
  fs.writeFileSync(path.join(dest,'release-key.enc.json'),JSON.stringify(envelope,null,2)+'\n');
  fs.writeFileSync(path.join(dest,'certificate.der'),cert);
  fs.writeFileSync(path.join(dest,'certificate-sha256.txt'),certificateSha256+'\n');
  fs.rmSync(keyFile);
  console.log('Encrypted signing backup created. Certificate SHA-256: '+certificateSha256);
} else if(mode==='restore') {
  const e=JSON.parse(fs.readFileSync(vaultPath,'utf8'));
  if(e.format!=='feishu-signing-v1'||e.package!=='dev.feishuwake'||e.alias!==alias||
     e.kdf!=='PBKDF2-HMAC-SHA256'||e.iterations!==600000||e.cipher!=='AES-256-GCM')
    throw new Error('Unexpected signing envelope metadata');
  const key=crypto.pbkdf2Sync(pass,Buffer.from(e.salt,'base64'),e.iterations,32,'sha256');
  const decipher=crypto.createDecipheriv('aes-256-gcm',key,Buffer.from(e.nonce,'base64'));
  decipher.setAAD(aad);decipher.setAuthTag(Buffer.from(e.tag,'base64'));
  const plain=Buffer.concat([decipher.update(Buffer.from(e.ciphertext,'base64')),decipher.final()]);
  fs.writeFileSync(keyFile,plain,{mode:0o600});plain.fill(0);
  run(['-exportcert','-keystore',keyFile,'-alias',alias,'-storepass:env','FEISHU_SIGNING_PASSWORD','-file',certFile]);
  const actual=crypto.createHash('sha256').update(fs.readFileSync(certFile)).digest('hex');
  if(actual!==e.certificate_sha256) throw new Error('Fixed signing certificate mismatch');
  // Password is random base64url; file paths are controlled Linux runner paths.
  fs.writeFileSync(path.join(root,'signing.properties'),
    'storeFile='+keyFile+'\nstorePassword='+pass+'\nkeyAlias='+alias+'\nkeyPassword='+pass+'\n',{mode:0o600});
  console.log('Fixed signing certificate restored: '+actual);
} else throw new Error('Expected init or restore');

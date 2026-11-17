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
const vaultSecret=process.env.FEISHU_SIGNING_VAULT||'';
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
if(process.argv[2]!=='restore') throw new Error('Fixed key already initialized; only restore is supported');
  if(!vaultSecret) throw new Error('Private signing backup Secret is missing');
  const e=JSON.parse(vaultSecret);
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
  const expected=fs.readFileSync(path.join(root,'signing','certificate-sha256.txt'),'utf8').trim();
  if(actual!==e.certificate_sha256||actual!==expected) throw new Error('Fixed signing certificate mismatch');
  // Password is random base64url; file paths are controlled Linux runner paths.
  fs.writeFileSync(path.join(root,'signing.properties'),
    'storeFile='+keyFile+'\nstorePassword='+pass+'\nkeyAlias='+alias+'\nkeyPassword='+pass+'\n',{mode:0o600});
  console.log('Fixed signing certificate restored: '+actual);

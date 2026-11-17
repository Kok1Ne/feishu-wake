"""Fail closed: release tasks require source-bound test evidence, never hand-written PASS defaults."""
import hashlib, json, pathlib, sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
def source_hash():
    h=hashlib.sha256()
    for p in sorted(ROOT.rglob('*')):
        rel=p.relative_to(ROOT)
        if not p.is_file() or any(x in rel.parts for x in ('build','.gradle','.idea','reports','.git')): continue
        if p.suffix not in ('.kt','.java','.xml','.kts','.py','.properties','.mjs','.yml','.yaml') or p.name in ('local.properties','signing.properties'): continue
        h.update(rel.as_posix().encode()); h.update(b'\0'); h.update(p.read_bytes())
    return h.hexdigest()
if __name__=='__main__':
    if '--hash' in sys.argv: print(source_hash()); sys.exit(0)
    path=ROOT/'release-evidence.json'
    if not path.exists(): sys.exit('RELEASE BLOCKED: no completed cloud verification evidence; no release APK may be generated.')
    e=json.loads(path.read_text(encoding='utf-8'))
    required=['debug_build','unit_tests','android_lint','install_launch','screen_off_alarm','wake_screen','dismiss_swipe','feishu_foreground','doze','reboot_restore','multiple_alarms','disable_cancel','reenable','edit_cancel_old','deduplicate','secure_lock_refused','notification_denied','process_reclaim','force_stop_recovery','notification_preflight','blocked_fsi_diagnosis','compatibility_wake','compatibility_revoked','ui_navigation']
    missing=[x for x in required if e.get('checks',{}).get(x)!='PASS']
    if e.get('source_sha256')!=source_hash(): missing.append('current source digest')
    if e.get('android_api')!=30 or not e.get('emulator_boot_completed'): missing.append('API 30 emulator boot evidence')
    if not (ROOT/'signing.properties').exists(): missing.append('stable release signing configuration')
    for item in e.get('evidence_files',[]):
        p=(ROOT/item['path']).resolve()
        if not p.is_relative_to(ROOT) or not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=item['sha256']: missing.append('evidence file integrity')
    if not e.get('evidence_files'): missing.append('raw evidence files')
    if missing: sys.exit('RELEASE BLOCKED: '+', '.join(missing))
    print('Release gate passed for source '+source_hash())

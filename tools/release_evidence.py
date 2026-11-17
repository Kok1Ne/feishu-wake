"""Build the release gate input only from this run's completed raw cloud evidence."""
import hashlib,json,os
from pathlib import Path
import xml.etree.ElementTree as ET
from release_gate import source_hash
ROOT=Path(__file__).resolve().parents[1]
if os.environ.get('GITHUB_ACTIONS')!='true':
    raise SystemExit('Evidence aggregation is cloud-only')
ci=ROOT/'reports/ci'
verified_run=os.environ.get('FEISHU_EVIDENCE_RUN_ID',os.environ['GITHUB_RUN_ID'])
raw=json.loads((ci/'feishu/android-host-results.json').read_text())
fixture=json.loads((ci/'mock/android-host-results.json').read_text())
status=json.loads((ci/'feishu/ci-status.json').read_text())
rows=raw['checks']
if raw['target']!='feishu' or not raw.get('extended_matrix'):
    raise SystemExit('Real Feishu extended matrix is required')
for kind,result in [('feishu',raw),('mock',fixture)]:
    if not result['checks'] or any(v.get('status')!='PASS' for v in result['checks'].values()):
        raise SystemExit(kind+' contains unsuccessful cloud checks')
    s=json.loads((ci/kind/'ci-status.json').read_text())
    if s.get('probe_exit_code')!=0 or s.get('source_commit')!=os.environ['GITHUB_SHA'] or s.get('run_id')!=verified_run:
        raise SystemExit(kind+' evidence does not belong to this successful source/run')
mapping={
 'install_launch':['install_launch'],
 'screen_off_alarm':['screen_off_route_b.initial_asleep','screen_off_route_b.alarm_delivered'],
 'wake_screen':['screen_off_route_b.awake'],
 'dismiss_swipe':['screen_off_route_b.initial_keyguard','screen_off_route_b.keyguard_dismissed','screen_off_route_b.unlock_before_launch'],
 'feishu_foreground':['screen_off_route_b.foreground'],
 'doze':['doze.initial_keyguard','doze.deep_idle_observed','doze.foreground_stable','doze.awake','doze.keyguard_dismissed','doze.single_trigger','doze.unlock_before_launch'],
 'reboot_restore':['reboot_restore.booted','reboot_restore.token_renewed','reboot_restore.schedule_present','reboot_restore.broadcast_logged','reboot_restore.foreground_stable','reboot_restore.single_trigger'],
 'multiple_alarms':['multiple_alarms.first_due','multiple_first.foreground_stable','multiple_alarms.second_registered','multiple_second.foreground_stable','multiple_alarms.next_day'],
 'disable_cancel':['disabled_cancel.no_trigger','disabled_cancel.asleep','disable_cancel.no_execution','disable_cancel.state_cleared'],
 'reenable':['reenable.next_due','reenable.foreground_stable','reenable.single_trigger'],
 'edit_cancel_old':['edit_cancel_old.no_old_trigger','edit_new_time.foreground_stable','edit_new_time.single_trigger'],
 'deduplicate':['multiple_first.single_trigger','multiple_second.single_trigger','multiple_alarms.no_duplicate'],
 'secure_lock_refused':['secure_lock.alarm_delivered','secure_lock.explicit_failure','secure_lock.no_launch_request','secure_lock.keyguard_retained','secure_lock.target_not_foreground'],
 'notification_denied':['notification_denied.alarm_delivered','notification_denied.explicit_failure','notification_denied.no_launch_request','notification_denied.target_not_foreground'],
 'process_reclaim':['process_reclaim.process_killed','process_reclaim.foreground_stable','process_reclaim.single_trigger'],
 'force_stop_recovery':['force_stop.no_execution','force_stop_recovery.next_registered','force_stop_recovery.foreground_stable','force_stop_recovery.single_trigger'],
}
for name,keys in mapping.items():
    if any(rows.get(k,{}).get('status')!='PASS' for k in keys):
        raise SystemExit('Missing successful evidence for '+name)
if rows.get('api30_boot',{}).get('status')!='PASS':
    raise SystemExit('API 30 boot was not observed')
tests=list((ROOT/'app/build/test-results/testDebugUnitTest').glob('TEST-*.xml'))
count=0
for f in tests:
    e=ET.parse(f).getroot()
    if int(e.get('errors','0')) or int(e.get('failures','0')): raise SystemExit('JVM test failure')
    count+=int(e.get('tests','0'))
if count<11: raise SystemExit('Incomplete JVM test reports')
lint=ROOT/'app/build/reports/lint-results-debug.xml'
issues=ET.parse(lint).getroot()
if any(i.get('severity') in ('Error','Fatal') for i in issues.findall('issue')):
    raise SystemExit('Android lint errors')
if 'BUILD SUCCESSFUL' not in (ci/'gradle.log').read_text():
    raise SystemExit('Successful Gradle build log missing')
evidence_paths=list(ci.rglob('*'))+tests+[lint]
evidence_files=[{'path':p.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
                for p in sorted(set(evidence_paths)) if p.is_file()]
checks={k:'PASS' for k in mapping}
checks.update(debug_build='PASS',unit_tests='PASS',android_lint='PASS')
evidence={'source_sha256':source_hash(),'source_commit':os.environ['GITHUB_SHA'],
          'run_id':verified_run,'release_run_id':os.environ['GITHUB_RUN_ID'],'android_api':30,'emulator_boot_completed':True,
          'checks':checks,'mapping':mapping,'jvm_test_count':count,
          'evidence_files':evidence_files,
          'limitations':['API 30 emulator, not realme hardware','Forced Doze is not long natural standby',
                         'Real Feishu launch is not attendance verification',
                         'Unlocked screen may show only a heads-up notification']}
(ROOT/'release-evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Evidence assembled from '+str(len(evidence_files))+' raw files; JVM tests: '+str(count))

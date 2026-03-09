##[debug]Evaluating: secrets.EMAIL_FROM
##[debug]Evaluating Index:
##[debug]..Evaluating secrets:
##[debug]..=> Object
##[debug]..Evaluating String:
##[debug]..=> 'EMAIL_FROM'
##[debug]=> '***'
##[debug]Result: '***'
##[debug]Evaluating: secrets.EMAIL_TO
##[debug]Evaluating Index:
##[debug]..Evaluating secrets:
##[debug]..=> Object
##[debug]..Evaluating String:
##[debug]..=> 'EMAIL_TO'
##[debug]=> '***'
##[debug]Result: '***'
##[debug]Evaluating: secrets.EMAIL_PASSWORD
##[debug]Evaluating Index:
##[debug]..Evaluating secrets:
##[debug]..=> Object
##[debug]..Evaluating String:
##[debug]..=> 'EMAIL_PASSWORD'
##[debug]=> '***'
##[debug]Result: '***'
##[debug]Evaluating condition for step: 'Run bin checker'
##[debug]Evaluating: success()
##[debug]Evaluating success:
##[debug]=> true
##[debug]Result: true
##[debug]Starting: Run bin checker
##[debug]Loading inputs
##[debug]Loading env
Run python bin_checker.py
##[debug]/usr/bin/bash -e /home/runner/work/_temp/c8f7b8ba-848c-4e2b-90b8-3c4aeb7d4a70.sh
2026-03-09 15:06:18,267 [INFO] Bin Checker started.
2026-03-09 15:06:18,267 [INFO] Address   : 79 Redhill Road
2026-03-09 15:06:18,267 [INFO] Notify    : ***
2026-03-09 15:06:18,267 [INFO] Schedule  : Every Tuesday at 18:30 GMT
2026-03-09 15:06:18,267 [INFO] RUN_NOW=true → running immediately for testing...
2026-03-09 15:06:18,267 [INFO] ==================================================
2026-03-09 15:06:18,267 [INFO] Running bin collection check...
2026-03-09 15:06:18,267 [INFO] Launching browser to scrape bin collection info...
2026-03-09 15:06:21,723 [INFO] Page loaded.
Error: -09 15:06:31,766 [ERROR] Job failed: Locator.wait_for: Timeout 10000ms exceeded.
Call log:
  - waiting for locator("input[type='text'], input[type='search']").first to be visible
Traceback (most recent call last):
  File "/home/runner/work/Bin-Checker/Bin-Checker/bin_checker.py", line 226, in run_job
    info = fetch_bin_info()
           ^^^^^^^^^^^^^^^^
  File "/home/runner/work/Bin-Checker/Bin-Checker/bin_checker.py", line 83, in fetch_bin_info
    search_input.wait_for(state="visible", timeout=10_000)
  File "/opt/hostedtoolcache/Python/3.11.14/x64/lib/python3.11/site-packages/playwright/sync_api/_generated.py", line 18074, in wait_for
    self._sync(self._impl_obj.wait_for(timeout=timeout, state=state))
  File "/opt/hostedtoolcache/Python/3.11.14/x64/lib/python3.11/site-packages/playwright/_impl/_sync_base.py", line 115, in _sync
    return task.result()
           ^^^^^^^^^^^^^
  File "/opt/hostedtoolcache/Python/3.11.14/x64/lib/python3.11/site-packages/playwright/_impl/_locator.py", line 710, in wait_for
    await self._frame.wait_for_selector(
  File "/opt/hostedtoolcache/Python/3.11.14/x64/lib/python3.11/site-packages/playwright/_impl/_frame.py", line 369, in wait_for_selector
    await self._channel.send(
  File "/opt/hostedtoolcache/Python/3.11.14/x64/lib/python3.11/site-packages/playwright/_impl/_connection.py", line 69, in send
    return await self._connection.wrap_api_call(
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/hostedtoolcache/Python/3.11.14/x64/lib/python3.11/site-packages/playwright/_impl/_connection.py", line 559, in wrap_api_call
    raise rewrite_error(error, f"{parsed_st['apiName']}: {error}") from None
playwright._impl._errors.TimeoutError: Locator.wait_for: Timeout 10000ms exceeded.
Call log:
  - waiting for locator("input[type='text'], input[type='search']").first to be visible

2026-03-09 15:06:33,052 [INFO] ✅ Email sent to ***

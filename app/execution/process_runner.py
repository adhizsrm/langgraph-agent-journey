import shutil
import subprocess
import time
from typing import Dict, Any


def run_cmd(cmd: str, cwd: str, timeout: int = 15) -> Dict[str, Any]:
    start = time.time()
    cmd_parts = cmd.split(" ")
    exe_path = shutil.which(cmd_parts[0]) or cmd_parts[0]
    actual_cmd = [exe_path] + cmd_parts[1:]
    try:
        proc = subprocess.run(
            actual_cmd,
            cwd=cwd,
            shell=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "success": proc.returncode == 0,
            "command": cmd,
            "exit_code": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "duration": time.time() - start,
        }
    except subprocess.TimeoutExpired as e:
        # Clean up if timeout
        return {
            "success": False,
            "command": cmd,
            "exit_code": -1,
            "stdout": e.stdout.decode() if e.stdout else "",
            "stderr": f"TIMEOUT EXPIRED ({timeout}s)",
            "duration": timeout,
        }
    except Exception as e:
        return {
            "success": False,
            "command": cmd,
            "exit_code": -1,
            "stdout": "",
            "stderr": str(e),
            "duration": time.time() - start,
        }

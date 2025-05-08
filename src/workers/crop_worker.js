const path = require('path');
const { spawn } = require('child_process');
const fs = require('fs');

function cropWorker(input, output) {
  const pythonPath = process.platform === 'win32'
    ? path.join(__dirname, '..', '..', 'venv', 'Scripts', 'python.exe')
    : path.join(__dirname, '..', '..', 'venv', 'bin', 'python3');
  const scriptPath = path.join(__dirname, '..', 'scripts', 'crop.py');

  // Save log in the same directory as the output file
  const logPath = path.join(path.dirname(output), 'crop_worker.log');
  function log(msg) {
    fs.appendFileSync(logPath, `[${new Date().toISOString()}] ${msg}\n`);
  }

  log(`START cropWorker: pythonPath=${pythonPath}, scriptPath=${scriptPath}, input=${input}, output=${output}`);

  return new Promise((resolve, reject) => {
    const args = [scriptPath, input, output];

    // Check if pythonPath exists
    if (!fs.existsSync(pythonPath)) {
      log(`ERROR: Python interpreter not found at ${pythonPath}`);
      return reject(new Error(`Python interpreter not found at ${pythonPath}`));
    }
    if (!fs.existsSync(scriptPath)) {
      log(`ERROR: crop.py not found at ${scriptPath}`);
      return reject(new Error(`crop.py not found at ${scriptPath}`));
    }

    const child = spawn(pythonPath, args, {
      stdio: ['ignore', 'pipe', 'pipe'],
      windowsHide: true
    });

    child.stdout.on('data', (data) => {
      log(`STDOUT: ${data.toString()}`);
    });
    child.stderr.on('data', (data) => {
      log(`STDERR: ${data.toString()}`);
    });

    child.on('error', (err) => {
      log(`SPAWN ERROR: ${err.message}`);
      reject(err);
    });

    child.on('exit', (code) => {
      log(`EXIT CODE: ${code}`);
      if (code === 0) resolve();
      else reject(new Error(`crop.py exited with code ${code}`));
    });
  });
}

module.exports = { cropWorker };

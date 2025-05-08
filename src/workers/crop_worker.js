const path = require('path');
const { spawn } = require('child_process');

function cropWorker(input, output) {
  const pythonPath = process.platform === 'win32'
    ? path.join(__dirname, '..', '..', 'venv', 'Scripts', 'python.exe')
    : path.join(__dirname, '..', '..', 'venv', 'bin', 'python3');
  const scriptPath = path.join(__dirname, '..', 'scripts', 'crop.py');

  return new Promise((resolve, reject) => {
    const args = [scriptPath, input, output];

    const child = spawn(pythonPath, args, {
      stdio: ['ignore', 'pipe', 'pipe'],
    });

    child.stdout.on('data', (data) => process.stdout.write(data.toString()));
    child.stderr.on('data', (data) => process.stderr.write(data.toString()));

    child.on('exit', (code) => {
      if (code === 0) resolve();
      else reject(new Error(`crop.py exited with code ${code}`));
    });
  });
}

module.exports = { cropWorker };

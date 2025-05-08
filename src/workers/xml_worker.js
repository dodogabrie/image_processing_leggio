const path = require('path');
const { spawn } = require('child_process');

function metadataWorker(inputXml, outputJson) {
  const pythonPath = process.platform === 'win32'
    ? path.join(__dirname, '..', '..', 'venv', 'Scripts', 'python.exe')
    : path.join(__dirname, '..', '..', 'venv', 'bin', 'python3');
  const scriptPath = path.join(__dirname, '..', 'scripts', 'extract_metadata.py');

  return new Promise((resolve, reject) => {
    const args = [scriptPath, inputXml, outputJson];
    const child = spawn(pythonPath, args, {
      stdio: ['ignore', 'pipe', 'pipe'],
    });

    child.stdout.on('data', (data) => process.stdout.write(data.toString()));
    child.stderr.on('data', (data) => process.stderr.write(data.toString()));

    child.on('exit', (code) => {
      if (code === 0) resolve();
      else reject(new Error(`extract_metadata.py exited with code ${code}`));
    });
  });
}

module.exports = { metadataWorker };

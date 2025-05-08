const path = require('path');
const { fork, spawn } = require('child_process');

function cropPageWorker(input, output, minArea = 200000) {
  const pythonPath = process.platform === 'win32'
    ? path.join(__dirname, 'venv', 'Scripts', 'python.exe')
    : path.join(__dirname, 'venv', 'bin', 'python3');
  const scriptPath = path.join(__dirname, 'scripts', 'crop.py');

  return new Promise((resolve, reject) => {
    const child = spawn(pythonPath, [ scriptPath, input, output, String(minArea) ], {
      stdio: ['ignore','pipe','pipe']
    });
    child.stdout.on('data', d => process.stdout.write(d));
    child.stderr.on('data', d => process.stderr.write(d));
    child.on('exit', code => {
      if (code === 0) return resolve(true);
      if (code === 2) return resolve(false);
      reject(new Error(`crop.py exited with code ${code}`));
    });
  });
}

function convertWorker(input, output, retries = 1) {
  return new Promise((resolve, reject) => {
    const child = fork(
      path.join(__dirname, 'workers', 'worker.js'),
      [ input, output ],
      {
        execPath: process.env.NODE_ENV === 'development' ? 'node' : process.execPath,
        stdio: ['ignore','pipe','pipe','ipc'],
        windowsHide: true
      }
    );
    child.stdout.on('data', d => process.stdout.write(d.toString()));
    child.stderr.on('data', d => process.stderr.write(d.toString()));
    child.on('exit', code => {
      if (code === 0) return resolve();
      if (retries > 0) return resolve(convertWorker(input, output, retries - 1));
      reject(new Error(`worker exited with code ${code}`));
    });
  });
}

function createThumbnailWorker(input, output, alias) {
  return new Promise((resolve, reject) => {
    const child = fork(
      path.join(__dirname, 'workers', 'thumbnail_worker.js'),
      [ input, output, alias ],
      {
        execPath: process.env.NODE_ENV === 'development' ? 'node' : process.execPath,
        stdio: ['ignore','pipe','pipe','ipc'],
        windowsHide: true
      }
    );
    child.stdout.on('data', d => process.stdout.write(d.toString()));
    child.stderr.on('data', d => process.stderr.write(d.toString()));
    child.on('exit', code => {
      if (code === 0) return resolve();
      reject(new Error(`thumbnail_worker exited with code ${code}`));
    });
  });
}

module.exports = {
  cropPageWorker,
  convertWorker,
  createThumbnailWorker
};

const { execSync } = require('child_process');
const { existsSync } = require('fs');
const path = require('path');

const venvPath = path.join(process.resourcesPath, 'venv');

function setupPythonEnv() {
  // Solo in produzione
  if (process.env.NODE_ENV === 'development') return;

  const pipDir = process.platform === 'win32' ? 'Scripts' : 'bin';
  const pipPath = path.join(venvPath, pipDir, process.platform === 'win32' ? 'pip.exe' : 'pip');

  if (existsSync(pipPath)) return;

  console.log('Creating virtualenv...');
  execSync(`${process.platform === 'win32' ? 'python' : 'python3'} -m venv venv`, {
    cwd: process.resourcesPath,
    stdio: 'inherit'
  });

  // Usa la copia unpacked di requirements.txt
  const requirementsPath = path.join(process.resourcesPath, 'app.asar.unpacked', 'requirements.txt');

  console.log('Installing Python dependencies...');
  execSync(`"${pipPath}" install -r "${requirementsPath}"`, {
    stdio: 'inherit'
  });
}

module.exports = { setupPythonEnv };

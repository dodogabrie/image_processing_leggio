const { execSync } = require('child_process');
const { existsSync } = require('fs');
const path = require('path');

const projectRoot = path.join(__dirname, '..');
const venvPath = path.join(process.resourcesPath, 'venv');

function setupPythonEnv() {
  // Solo in produzione
  if (process.env.NODE_ENV === 'development') return;

  const pipPath = path.join(venvPath, process.platform === 'win32' ? 'Scripts' : 'bin');

  if (existsSync(pipPath)) return; // già presente

  // Crea venv
  console.log('Creating virtualenv...');
  execSync('python3 -m venv venv', { cwd: process.resourcesPath, stdio: 'inherit' });

  const pip = process.platform === 'win32'
    ? path.join(venvPath, 'Scripts', 'pip.exe')
    : path.join(venvPath, 'bin', 'pip');
  const requirementsPath = path.join(process.resourcesPath, 'requirements.txt');
  execSync(`${pip} install -r "${requirementsPath}"`, { stdio: 'inherit' });
}

module.exports = { setupPythonEnv };

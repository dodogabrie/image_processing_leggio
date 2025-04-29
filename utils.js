const fs = require('fs').promises;
const path = require('path');

async function getAllFolders(dir) {
  let folders = [dir];
  const files = await fs.readdir(dir);
  for (const file of files) {
    const fullPath = path.join(dir, file);
    let stat;
    try {
      stat = await fs.stat(fullPath);
    } catch {
      continue;
    }
    if (stat.isDirectory() && file !== '$RECYCLE.BIN') {
      folders = folders.concat(await getAllFolders(fullPath));
    }
  }
  return folders;
}

module.exports = { getAllFolders };

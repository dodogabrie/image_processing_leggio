// organize_by_xml.js
import fs from 'fs/promises';
import path from 'path';
import slugify from 'slugify';
import crypto from 'crypto';
import Logger from '../Logger.js';

const logger = new Logger();

const THUMBNAIL_TYPES = ['low_quality', 'gallery'];

const MAX_FOLDER_SLUG = 60;
const MAX_FILENAME_BASE = 80;

function shortHash(value) {
  return crypto.createHash('sha1').update(value).digest('hex').slice(0, 6);
}

function clampSlug(value, maxLength) {
  const slug = slugify(value, { lower: true, strict: true });
  if (slug.length <= maxLength) return slug;
  const suffix = shortHash(slug);
  const trimmed = slug.slice(0, Math.max(1, maxLength - (suffix.length + 1))).replace(/-+$/g, '');
  return `${trimmed}-${suffix}`;
}

function clampFileBase(value, maxLength) {
  const safe = value.replace(/[\\/:*?"<>|]/g, '-');
  if (safe.length <= maxLength) return safe;
  const suffix = shortHash(safe);
  const trimmed = safe.slice(0, Math.max(1, maxLength - (suffix.length + 1))).replace(/-+$/g, '');
  return `${trimmed}-${suffix}`;
}

/**
 * Build index of all webp files for quick lookup.
 * @param {string} rootDir
 * @returns {Promise<Map<string, string>>}
 */
async function indexWebpFiles(rootDir) {
  const fileIndex = new Map();

  async function scanDir(dir) {
    const entries = await fs.readdir(dir, { withFileTypes: true });

    for (const entry of entries) {
      const fullPath = path.join(dir, entry.name);

      if (entry.isDirectory()) {
        await scanDir(fullPath);
      } else if (entry.name.toLowerCase().endsWith('.webp')) {
        const basename = path.basename(entry.name, '.webp');
        fileIndex.set(basename, fullPath);
      }
    }
  }

  await scanDir(rootDir);
  return fileIndex;
}

/**
 * Copy thumbnails for a given image identifier.
 * @param {string} identifier
 * @param {string} webpDir
 * @param {string} destThumbnailDir
 */
async function copyThumbnails(identifier, webpDir, destThumbnailDir, baseName) {
  await fs.mkdir(destThumbnailDir, { recursive: true });

  const thumbnailsDir = path.join(webpDir, 'thumbnails');

  for (const thumbType of THUMBNAIL_TYPES) {
    const thumbName = `${identifier}_${thumbType}.webp`;
    const srcThumb = path.join(thumbnailsDir, thumbName);
    const destThumb = path.join(destThumbnailDir, `${baseName}_${thumbType}.webp`);

    try {
      await fs.copyFile(srcThumb, destThumb);
    } catch (err) {
      logger.warn(`Thumbnail not found: ${thumbName}`);
    }
  }
}

/**
 * Extract identifier from XML file href.
 * Example: "./DOC_001/jpeg300/IMG_0001.jpg" -> "IMG_0001"
 * @param {string} href
 * @returns {string}
 */
function extractIdentifier(href) {
  if (!href) return null;
  const basename = path.basename(href);
  return path.parse(basename).name; // removes extension
}

/**
 * Organize images from XML metadata.
 * @param {Array<string>} metadataJsonPaths - Array of metadata JSON file paths
 * @param {string} webpDir - Directory containing processed WebP images
 * @param {string} outputDir - Base output directory
 * @param {Function} progressCallback - Progress callback function
 */
export async function organizeFromXml(metadataJsonPaths, webpDir, outputDir, progressCallback = () => {}) {
  logger.info(`Organizing ${metadataJsonPaths.length} XML documents`);

  // Create output directories
  const organizedDir = path.join(outputDir, 'organized');
  const thumbnailsDir = path.join(outputDir, 'organized_thumbnails');
  await fs.mkdir(organizedDir, { recursive: true });
  await fs.mkdir(thumbnailsDir, { recursive: true });

  // Index all webp files
  const fileIndex = await indexWebpFiles(webpDir);
  logger.info(`Indexed ${fileIndex.size} WebP files`);

  let processedCount = 0;
  const totalCount = metadataJsonPaths.length;

  for (const jsonPath of metadataJsonPaths) {
    try {
      // Read metadata JSON
      const rawData = await fs.readFile(jsonPath, 'utf-8');
      const metadata = JSON.parse(rawData);

      const docMeta = metadata.document || {};
      const images = metadata.images || [];

      // Use identifier as folder name (no groupBy)
      const folderName = docMeta.identifier || 'unknown';
      const slug = clampSlug(folderName, MAX_FOLDER_SLUG);

      // Create document folder
      const docDir = path.join(organizedDir, slug);
      const docThumbnailDir = path.join(thumbnailsDir, slug);
      await fs.mkdir(docDir, { recursive: true });
      await fs.mkdir(docThumbnailDir, { recursive: true });

      logger.info(`Processing document: ${groupBy} (${images.length} images)`);

      // Process each image
      const processedImages = [];
      for (const img of images) {
        const identifier = extractIdentifier(img.filename || img.filepath);
        if (!identifier) {
          logger.warn(`Skipping image with no identifier`);
          continue;
        }

        // Find webp file
        const webpPath = fileIndex.get(identifier);
        if (!webpPath) {
          logger.warn(`WebP not found for identifier: ${identifier}`);
          continue;
        }

        // Copy image to organized folder
        const baseName = clampFileBase(identifier, MAX_FILENAME_BASE);
        const destName = `${baseName}.webp`;
        const destPath = path.join(docDir, destName);
        await fs.copyFile(webpPath, destPath);

        // Copy thumbnails
        await copyThumbnails(identifier, webpDir, docThumbnailDir, baseName);

        processedImages.push({
          ...img,
          organized_filename: destName
        });
      }

      // Write metadata JSON to document folder
      const docMetadataPath = path.join(docDir, 'metadata.json');
      await fs.writeFile(docMetadataPath, JSON.stringify({
        document: docMeta,
        images: processedImages
      }, null, 2));

      processedCount++;
      progressCallback({
        type: 'xml_organize',
        current: processedCount,
        total: totalCount,
        document: groupBy
      });

    } catch (err) {
      logger.error(`Error processing ${jsonPath}: ${err.message}`);
    }
  }

  logger.info(`XML organization complete: ${processedCount}/${totalCount} documents`);

  return {
    success: true,
    processedCount,
    totalCount
  };
}

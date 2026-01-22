// File: backend/utils/tabular-reader.js
import fs from 'fs/promises';
import * as fsSync from 'fs';
import path from 'path';
import { parse } from 'csv-parse/sync';
import xlsx from 'xlsx';

const XLSX_EXTENSIONS = new Set(['.xlsx', '.xls']);

function isXlsxPath(filePath) {
  return XLSX_EXTENSIONS.has(path.extname(filePath).toLowerCase());
}

function filterEmptyRecords(records) {
  return records.filter(record =>
    Object.values(record).some(value => value != null && String(value).trim() !== '')
  );
}

function readXlsxSheet(filePath) {
  const workbook = xlsx.readFile(filePath, { cellDates: false });
  const sheetName = workbook.SheetNames[0];
  if (!sheetName) return null;
  return workbook.Sheets[sheetName] || null;
}

function getCsvParseOptions(withColumns = false) {
  return {
    columns: withColumns,
    skip_empty_lines: true,
    bom: true,
    relax_column_count: true,
    delimiter: [',', ';']
  };
}

export async function readTabularHeaders(filePath) {
  if (!filePath || !fsSync.existsSync(filePath)) {
    throw new Error(`File not found: ${filePath}`);
  }

  if (isXlsxPath(filePath)) {
    const sheet = readXlsxSheet(filePath);
    if (!sheet) return [];
    const rows = xlsx.utils.sheet_to_json(sheet, { header: 1, defval: '' });
    const headers = rows[0] || [];
    return headers.map(header => String(header ?? '').trim());
  }

  const content = await fs.readFile(filePath);
  const records = parse(content, getCsvParseOptions(false));
  return records.length > 0 ? records[0] : [];
}

export async function readTabularRecords(filePath) {
  if (!filePath || !fsSync.existsSync(filePath)) {
    throw new Error(`File not found: ${filePath}`);
  }

  if (isXlsxPath(filePath)) {
    const sheet = readXlsxSheet(filePath);
    if (!sheet) return [];
    const records = xlsx.utils.sheet_to_json(sheet, { defval: '' });
    return filterEmptyRecords(records);
  }

  const content = await fs.readFile(filePath);
  return parse(content, getCsvParseOptions(true));
}

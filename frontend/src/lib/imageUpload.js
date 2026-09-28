/**
 * Görseli yüklemeden önce belleğe okur ve gerekirse küçültür.
 *
 * iOS Safari, `<input type="file">`'dan gelen bir File'ı istek anında okuyamazsa
 * multipart gövdesinden o parçayı sessizce düşürebiliyor; backend `file` alanını
 * hiç görmeden 422 dönüyor. Baytları burada okumak bu durumu yükleme öncesinde
 * yakalıyor ve her zaman dosya adı olan gerçek bir Blob gönderilmesini sağlıyor.
 */

import { formatApiError } from "./apiError";

const TRANSPARENT_TYPES = new Set(["image/png", "image/webp", "image/gif"]);

/** Yükleme hatasını kullanıcıya gösterilecek metne çevirir (asla "[object Object]" değil). */
export function imageUploadErrorText(err, t) {
  if (err?.message === "file_unreadable") {
    return t("settings.profile.fileUnreadable");
  }
  return formatApiError(err, t, err?.message || t("common.error", "Error"));
}

function baseName(name) {
  const clean = String(name || "image").replace(/\.[^.]*$/, "").replace(/[^\w-]+/g, "_");
  return clean.slice(0, 40) || "image";
}

function loadImage(blob) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(blob);
    const img = new Image();
    img.onload = () => {
      URL.revokeObjectURL(url);
      resolve(img);
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("image decode failed"));
    };
    img.src = url;
  });
}

/**
 * @param {File} file
 * @param {{ maxDimension?: number }} [options]
 * @returns {Promise<{ blob: Blob, filename: string }>}
 * @throws Error("file_unreadable") — dosyanın baytları okunamadıysa
 */
export async function prepareImageForUpload(file, { maxDimension = 1600 } = {}) {
  let buffer;
  try {
    buffer = await file.arrayBuffer();
  } catch (e) {
    throw new Error("file_unreadable");
  }
  if (!buffer || buffer.byteLength === 0) {
    throw new Error("file_unreadable");
  }

  const sourceType = file.type || "image/jpeg";
  const original = new Blob([buffer], { type: sourceType });
  const keepAlpha = TRANSPARENT_TYPES.has(sourceType);
  const outType = keepAlpha ? "image/png" : "image/jpeg";
  const ext = keepAlpha ? "png" : "jpg";
  const filename = `${baseName(file.name)}.${ext}`;

  try {
    const img = await loadImage(original);
    const scale = Math.min(1, maxDimension / Math.max(img.naturalWidth, img.naturalHeight));
    const width = Math.max(1, Math.round(img.naturalWidth * scale));
    const height = Math.max(1, Math.round(img.naturalHeight * scale));
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext("2d");
    if (!keepAlpha) {
      ctx.fillStyle = "#ffffff";
      ctx.fillRect(0, 0, width, height);
    }
    ctx.drawImage(img, 0, 0, width, height);
    const blob = await new Promise((resolve) => canvas.toBlob(resolve, outType, 0.9));
    if (blob && blob.size > 0) {
      return { blob, filename };
    }
  } catch (_) {
    // Tarayıcı formatı çözemedi (ör. bazı HEIC'ler); ham baytlarla devam edilir.
  }

  const rawExt = (sourceType.split("/")[1] || "jpg").replace("jpeg", "jpg");
  return { blob: original, filename: `${baseName(file.name)}.${rawExt}` };
}

/**
 * Hazırlanan görseli FormData'ya `file` alanı olarak ekler.
 * @param {File} file
 * @param {{ maxDimension?: number }} [options]
 */
export async function buildImageFormData(file, options) {
  const { blob, filename } = await prepareImageForUpload(file, options);
  const fd = new FormData();
  fd.append("file", blob, filename);
  return fd;
}

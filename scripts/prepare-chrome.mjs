import { cp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { deflateSync } from "node:zlib";

const root = path.resolve(fileURLToPath(new URL("..", import.meta.url)));
const source = path.join(root, "extension");
const chromeSource = path.join(root, "chrome");
const output = path.join(root, "build", "chrome");

if (!output.startsWith(`${root}${path.sep}`)) {
  throw new Error("La carpeta de compilación quedó fuera del proyecto.");
}

await rm(output, { recursive: true, force: true });
await mkdir(path.dirname(output), { recursive: true });
await cp(source, output, { recursive: true });
await cp(
  path.join(chromeSource, "manifest.json"),
  path.join(output, "manifest.json")
);

for (const relativePath of ["popup/exporter.js"]) {
  const target = path.join(output, relativePath);
  const firefoxCode = await readFile(target, "utf8");
  await writeFile(target, firefoxCode.replaceAll("browser.", "chrome."), "utf8");
}

await cp(
  path.join(chromeSource, "content", "session.js"),
  path.join(output, "content", "session.js")
);

await mkdir(path.join(output, "icons"), { recursive: true });
for (const size of [16, 32, 48, 128]) {
  await writeFile(
    path.join(output, "icons", `of-backup-${size}.png`),
    createIcon(size)
  );
}

console.log(`Chrome preparado en ${path.relative(root, output)}`);

function createIcon(size) {
  const stride = 1 + size * 4;
  const raw = Buffer.alloc(stride * size);
  const scale = size / 96;

  for (let y = 0; y < size; y += 1) {
    const row = y * stride;
    raw[row] = 0;
    for (let x = 0; x < size; x += 1) {
      const px = (x + 0.5) / scale;
      const py = (y + 0.5) / scale;
      const offset = row + 1 + x * 4;
      const radius = 22;
      const cornerX = Math.max(radius - px, 0, px - (96 - radius));
      const cornerY = Math.max(radius - py, 0, py - (96 - radius));
      const inside = cornerX * cornerX + cornerY * cornerY <= radius * radius;

      if (!inside) {
        continue;
      }

      let color = [17, 21, 29, 255];
      const distance = Math.hypot(px - 48, py - 48);
      if (distance >= 18 && distance <= 34) {
        const blend = Math.min(1, Math.max(0, (px + py - 24) / 144));
        color = [
          Math.round(22 * (1 - blend)),
          Math.round(199 * (1 - blend) + 119 * blend),
          Math.round(255 * (1 - blend) + 217 * blend),
          255
        ];
      }

      const arrow =
        distanceToSegment(px, py, 48, 37, 48, 59) <= 3 ||
        distanceToSegment(px, py, 39, 50, 48, 59) <= 3 ||
        distanceToSegment(px, py, 57, 50, 48, 59) <= 3;
      if (arrow) {
        color = [255, 255, 255, 255];
      }

      raw[offset] = color[0];
      raw[offset + 1] = color[1];
      raw[offset + 2] = color[2];
      raw[offset + 3] = color[3];
    }
  }

  const header = Buffer.alloc(13);
  header.writeUInt32BE(size, 0);
  header.writeUInt32BE(size, 4);
  header[8] = 8;
  header[9] = 6;
  return Buffer.concat([
    Buffer.from("89504e470d0a1a0a", "hex"),
    pngChunk("IHDR", header),
    pngChunk("IDAT", deflateSync(raw)),
    pngChunk("IEND", Buffer.alloc(0))
  ]);
}

function distanceToSegment(px, py, x1, y1, x2, y2) {
  const dx = x2 - x1;
  const dy = y2 - y1;
  const lengthSquared = dx * dx + dy * dy;
  const projection = Math.max(
    0,
    Math.min(1, ((px - x1) * dx + (py - y1) * dy) / lengthSquared)
  );
  return Math.hypot(px - (x1 + projection * dx), py - (y1 + projection * dy));
}

function pngChunk(type, data) {
  const typeBuffer = Buffer.from(type, "ascii");
  const chunk = Buffer.alloc(12 + data.length);
  chunk.writeUInt32BE(data.length, 0);
  typeBuffer.copy(chunk, 4);
  data.copy(chunk, 8);
  chunk.writeUInt32BE(crc32(Buffer.concat([typeBuffer, data])), 8 + data.length);
  return chunk;
}

function crc32(buffer) {
  let crc = 0xffffffff;
  for (const byte of buffer) {
    crc ^= byte;
    for (let bit = 0; bit < 8; bit += 1) {
      crc = (crc >>> 1) ^ (crc & 1 ? 0xedb88320 : 0);
    }
  }
  return (crc ^ 0xffffffff) >>> 0;
}

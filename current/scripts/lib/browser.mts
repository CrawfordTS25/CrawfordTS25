/**
 * Chromium launcher that tolerates a pre-provisioned browser whose build
 * revision does not match the installed Playwright package. Falls back to the
 * PLAYWRIGHT_BROWSERS_PATH executable before giving up.
 */

import { existsSync } from 'node:fs';
import { join } from 'node:path';
import { chromium, type Browser, type LaunchOptions } from 'playwright';

function candidates(): string[] {
  const base = process.env.PLAYWRIGHT_BROWSERS_PATH;
  const out: string[] = [];
  if (process.env.CHROMIUM_PATH) out.push(process.env.CHROMIUM_PATH);
  if (base) {
    out.push(join(base, 'chromium'));
    out.push(join(base, 'chromium-1194', 'chrome-linux', 'chrome'));
    out.push(join(base, 'chromium_headless_shell-1194', 'chrome-linux', 'headless_shell'));
  }
  out.push('/usr/bin/chromium', '/usr/bin/google-chrome');
  return out;
}

export async function launchChromium(options: LaunchOptions = {}): Promise<Browser> {
  try {
    return await chromium.launch(options);
  } catch (err) {
    for (const path of candidates()) {
      if (!existsSync(path)) continue;
      try {
        return await chromium.launch({ ...options, executablePath: path });
      } catch {
        // try the next candidate
      }
    }
    throw err;
  }
}

const fs = require('fs');
const http = require('http');

async function test() {
    // import presets
    const text = fs.readFileSync('apps/web/config/presets.ts', 'utf8');
    // Extract everything inside presets array
    const jsonStr = text.substring(text.indexOf('presets:') > -1 ? text.indexOf('presets:') : text.indexOf('presets: PresetConfig[] = ['));
    // Since it's TS, it's easier to just POST the manual ones we care about directly.
}
test();

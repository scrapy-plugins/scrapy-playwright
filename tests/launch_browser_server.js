const { chromium } = require('playwright');  // Or 'webkit' or 'firefox'.

(async () => {
    const browserServer = await chromium.launchServer({
        host: 'localhost',
        port: process.argv[2],
        wsPath: process.argv[3]
    });
})();

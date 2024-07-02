// used to start a browser server to test the PLAYWRIGHT_CONNECT_URL setting
// usage:
//   node launch_browser_server.js PORT WS_PATH

const { chromium } = require('playwright');  // Or 'webkit' or 'firefox'.

(async () => {
    const browserServer = await chromium.launchServer({
        host: 'localhost',
        port: process.argv[2],
        wsPath: process.argv[3]
    });
})();

const { bootEchoShell } = require('./electron-shell');

bootEchoShell({
  mode: 'desktop',
  defaultServerAddress: process.env.ECHO_SERVER_ADDRESS || '',
  showDevTools: process.env.ECHO_OPEN_DEVTOOLS === '1'
});

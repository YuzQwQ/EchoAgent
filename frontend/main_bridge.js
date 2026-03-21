const { bootEchoShell } = require('./electron-shell');

function readServerArg() {
    const cliArg = process.argv.find((arg) => arg.startsWith('--server='));
    if (cliArg) {
        return cliArg.slice('--server='.length).trim();
    }
    return process.env.ECHO_BRIDGE_SERVER || '';
}

bootEchoShell({
    mode: 'bridge',
    defaultServerAddress: readServerArg(),
    showDevTools: process.env.ECHO_OPEN_DEVTOOLS === '1',
});

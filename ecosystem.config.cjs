
module.exports = {
  apps: [
    {
      name: "local-file-server",
      script: "server.py",
      cwd: "C:/Users/Dana Anika/mcp-file-server-project",
      interpreter:
        "C:/Users/Dana Anika/mcp-file-server-project/.venv/Scripts/python.exe",
      exec_mode: "fork",
      instances: 1,
      autorestart: true,
      watch: false,
      env: {
        MCP_SERVER_URL: process.env.MCP_SERVER_URL,
        MCP_DEMO_USERNAME: process.env.MCP_DEMO_USERNAME,
        MCP_DEMO_PASSWORD: process.env.MCP_DEMO_PASSWORD
      }
    }
  ]
};

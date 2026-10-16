

$ErrorActionPreference = "Stop"

$ProjectDir = "C:\Users\Dana Anika\mcp-file-server-project"
Set-Location $ProjectDir

$env:MCP_SERVER_URL = "https://induction-caution-bedrooms-mostly.trycloudflare.com"
$env:MCP_DEMO_USERNAME = Read-Host "Enter your MCP demo username"

$SecurePassword = Read-Host "Enter your MCP demo password" -AsSecureString
$BSTR = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecurePassword)

try {
    $env:MCP_DEMO_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($BSTR)

    pm2 start .\ecosystem.config.cjs --only local-file-server --update-env
}
finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($BSTR)
    Remove-Item Env:\MCP_DEMO_USERNAME -ErrorAction SilentlyContinue
    Remove-Item Env:\MCP_DEMO_PASSWORD -ErrorAction SilentlyContinue
}

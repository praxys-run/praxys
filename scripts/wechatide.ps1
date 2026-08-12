param(
    [Parameter(Mandatory = $true)]
    [string] $InstallRoot,

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $WechatIdeArgs
)

$ErrorActionPreference = "Stop"

$command = Join-Path $installRoot "wechatide.cmd"
if (-not (Test-Path -LiteralPath $command -PathType Leaf)) {
    throw "wechatide.cmd was not found at $command"
}

Push-Location $env:SystemRoot
try {
    & $command @WechatIdeArgs
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}

New-Service -Name "DIZApp01" -Description "FHIR Query Tool" -Binary (Join-Path (Get-Location) 'DIZApp01Service.exe') -StartupType Automatic
$services = Get-Service -Name "DIZApp01"
if ($services.length -eq 0) {
	Write-Output("Service installation failed.")
} else {
	Write-Output("Starting service...")
	foreach ($service in $services) {
		Start-Service -InputObject $service
	}
	Write-Output("Service installation finished. Check if service runs properly.")
}
Start-Sleep -Seconds 5
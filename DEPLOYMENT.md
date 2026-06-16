# Production Deployment

The production image contains the React frontend and FastAPI backend. Azure
Functions is deployed separately as a zip package.

## Validate

```powershell
cd backend
python -m pytest tests -q

cd ..\frontend
npm.cmd ci
npm.cmd run build

cd ..
docker build -t usms-chatbot:1.0.0 .
docker image inspect usms-chatbot:1.0.0
```

## Push application image

Temporarily enable ACR public access through Terraform before running:

```powershell
az acr login --name acraichatbotprodcin001
docker tag usms-chatbot:1.0.0 acraichatbotprodcin001.azurecr.io/usms-chatbot:1.0.0
docker push acraichatbotprodcin001.azurecr.io/usms-chatbot:1.0.0
az acr repository show-tags --name acraichatbotprodcin001 --repository usms-chatbot --output table
az webapp restart --resource-group rg-aichatbot-prod-cin-workload-001 --name app-aichatbot-prod-cin-001
```

## Publish Function

Create the zip from the contents of `azure_function`, so `host.json` is at the
archive root:

```powershell
cd azure_function
Compress-Archive -Path function_app.py,host.json,requirements.txt -DestinationPath ..\function-release.zip -Force
cd ..
az functionapp deployment source config-zip --resource-group rg-aichatbot-prod-cin-workload-001 --name func-aichatbot-prod-cin-001 --src .\function-release.zip --build-remote true
```

Restore ACR and Function public access to disabled through Terraform after both
deployments complete.

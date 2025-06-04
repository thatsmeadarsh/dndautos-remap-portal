# DnD Autos ECU Remap Portal

A web application for managing ECU remapping requests.

## Deployment to Azure Web App

### Prerequisites

- Azure account
- Azure CLI installed and logged in

### Setup Azure Resources

1. Create a Resource Group:
```
az group create --name dndautos-rg --location eastus
```

2. Create an Azure Storage Account:
```
az storage account create --name dndautosstorage --resource-group dndautos-rg --location eastus --sku Standard_LRS
```

3. Create a Blob Container:
```
az storage container create --name ecufiles --account-name dndautosstorage
```

4. Get Storage Connection String:
```
az storage account show-connection-string --name dndautosstorage --resource-group dndautos-rg
```

5. Create an App Service Plan:
```
az appservice plan create --name dndautos-plan --resource-group dndautos-rg --sku B1 --is-linux
```

6. Create a Web App:
```
az webapp create --name dndautos-remap-portal --resource-group dndautos-rg --plan dndautos-plan --runtime "PYTHON|3.10"
```

### Configure Environment Variables

Set the required environment variables:

```
az webapp config appsettings set --name dndautos-remap-portal --resource-group dndautos-rg --settings SECRET_KEY="your-secret-key" AZURE_STORAGE_ACCOUNT="dndautosstorage" AZURE_STORAGE_CONNECTION_STRING="your-connection-string" AZURE_STORAGE_CONTAINER="ecufiles" ENABLE_AZURE_STORAGE="true"
```

### Deploy the Application

1. Initialize Git repository (if not already done):
```
git init
git add .
git commit -m "Initial commit"
```

2. Deploy to Azure:
```
az webapp deployment source config-local-git --name dndautos-remap-portal --resource-group dndautos-rg
git remote add azure <git-url-from-previous-command>
git push azure main
```

### Access the Application

The application will be available at:
```
https://dndautos-remap-portal.azurewebsites.net
```
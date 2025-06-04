// Vehicle API integration for DnD Autos ECU Remap Portal

document.addEventListener('DOMContentLoaded', function() {
    // Elements
    const regNumberInput = document.getElementById('registration_number');
    const lookupButton = document.getElementById('lookup_vehicle');
    const vehicleMakeSelect = document.getElementById('vehicle_make');
    const vehicleModelSelect = document.getElementById('vehicle_model');
    const vehicleYearInput = document.getElementById('vehicle_year');
    const lookupResult = document.getElementById('lookup_result');
    
    // Load makes on page load
    if (vehicleMakeSelect) {
        loadVehicleMakes();
    }
    
    // Registration lookup
    if (lookupButton) {
        lookupButton.addEventListener('click', function(e) {
            e.preventDefault();
            const regNumber = regNumberInput.value.trim();
            if (regNumber) {
                lookupVehicleByRegistration(regNumber);
            } else {
                showLookupError("Please enter a registration number");
            }
        });
    }
    
    // Make selection change
    if (vehicleMakeSelect) {
        vehicleMakeSelect.addEventListener('change', function() {
            const selectedMake = this.value;
            if (selectedMake) {
                loadVehicleModels(selectedMake);
            } else {
                clearSelect(vehicleModelSelect, "Select Model");
            }
        });
    }
    
    // Functions to interact with vehicle APIs
    function loadVehicleMakes() {
        // Show loading state
        if (vehicleMakeSelect) {
            vehicleMakeSelect.innerHTML = '<option value="">Loading makes...</option>';
            vehicleMakeSelect.disabled = true;
        }
        
        // Use hardcoded Indian makes instead of API call
        const indianMakes = [
            'MARUTI SUZUKI', 'TATA', 'MAHINDRA', 'HYUNDAI', 'HONDA', 
            'TOYOTA', 'KIA', 'FORD', 'RENAULT', 'VOLKSWAGEN', 'SKODA',
            'MG', 'JEEP', 'NISSAN', 'DATSUN', 'FIAT', 'MERCEDES-BENZ',
            'BMW', 'AUDI', 'LEXUS', 'VOLVO', 'JAGUAR', 'LAND ROVER'
        ];
        
        if (vehicleMakeSelect) {
            vehicleMakeSelect.disabled = false;
            clearSelect(vehicleMakeSelect, "Select Make");
            
            // Sort makes alphabetically
            indianMakes.sort();
            
            indianMakes.forEach(make => {
                const option = document.createElement('option');
                option.value = make;
                option.textContent = make;
                vehicleMakeSelect.appendChild(option);
            });
        }
    }
    
    function loadVehicleModels(make) {
        if (vehicleModelSelect) {
            vehicleModelSelect.innerHTML = '<option value="">Loading models...</option>';
            vehicleModelSelect.disabled = true;
        }
        
        // Use hardcoded models instead of API call
        const indianModels = {
            'MARUTI SUZUKI': ['Swift', 'Baleno', 'Dzire', 'Ertiga', 'Brezza', 'Alto', 'Wagon R', 'Celerio'],
            'TATA': ['Nexon', 'Harrier', 'Safari', 'Tiago', 'Altroz', 'Punch', 'Tigor'],
            'MAHINDRA': ['Scorpio', 'XUV700', 'XUV300', 'Thar', 'Bolero', 'Marazzo'],
            'HYUNDAI': ['Creta', 'i20', 'Venue', 'i10', 'Verna', 'Tucson', 'Alcazar'],
            'HONDA': ['City', 'Amaze', 'WR-V', 'Jazz', 'Civic'],
            'TOYOTA': ['Innova', 'Fortuner', 'Glanza', 'Urban Cruiser', 'Camry'],
            'KIA': ['Seltos', 'Sonet', 'Carnival', 'Carens'],
            'FORD': ['EcoSport', 'Figo', 'Aspire', 'Endeavour'],
            'RENAULT': ['Kwid', 'Triber', 'Kiger', 'Duster'],
            'VOLKSWAGEN': ['Polo', 'Vento', 'Taigun', 'Tiguan'],
            'SKODA': ['Kushaq', 'Slavia', 'Octavia', 'Superb']
        };
        
        if (vehicleModelSelect) {
            vehicleModelSelect.disabled = false;
            clearSelect(vehicleModelSelect, "Select Model");
            
            const makeUpperCase = make.toUpperCase();
            if (indianModels[makeUpperCase]) {
                // Sort models alphabetically
                indianModels[makeUpperCase].sort();
                
                indianModels[makeUpperCase].forEach(model => {
                    const option = document.createElement('option');
                    option.value = model;
                    option.textContent = model;
                    vehicleModelSelect.appendChild(option);
                });
            } else {
                // For makes not in our list, add some generic models
                ['Base', 'Standard', 'Deluxe', 'Premium', 'Sport'].forEach(model => {
                    const option = document.createElement('option');
                    option.value = model;
                    option.textContent = model;
                    vehicleModelSelect.appendChild(option);
                });
            }
        }
    }
    
    function lookupVehicleByRegistration(regNumber) {
        // Show loading state
        lookupResult.innerHTML = '<div class="spinner-border text-primary" role="status"><span class="visually-hidden">Loading...</span></div>';
        lookupResult.classList.remove('d-none', 'alert-danger', 'alert-success');
        lookupResult.classList.add('alert', 'alert-info');
        
        // Call the vehicle registration API
        fetch('/api/vehicle-lookup', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ registration: regNumber })
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                showLookupError(data.error);
                return;
            }
            
            // Update form fields with the returned data
            if (data.make) {
                // Find and select the make in the dropdown
                const makeOption = Array.from(vehicleMakeSelect.options).find(option => 
                    option.value.toLowerCase() === data.make.toLowerCase());
                
                if (makeOption) {
                    vehicleMakeSelect.value = makeOption.value;
                    // Load models for this make
                    loadVehicleModels(makeOption.value);
                    
                    // Set the model after a short delay to ensure models are loaded
                    setTimeout(() => {
                        if (data.model) {
                            const modelOption = Array.from(vehicleModelSelect.options).find(option => 
                                option.value.toLowerCase().includes(data.model.toLowerCase()));
                            
                            if (modelOption) {
                                vehicleModelSelect.value = modelOption.value;
                            } else {
                                // If exact match not found, add the model from API
                                const newOption = document.createElement('option');
                                newOption.value = data.model;
                                newOption.textContent = data.model;
                                vehicleModelSelect.appendChild(newOption);
                                vehicleModelSelect.value = data.model;
                            }
                        }
                    }, 500);
                } else {
                    // If make not found in dropdown, add it
                    const newOption = document.createElement('option');
                    newOption.value = data.make;
                    newOption.textContent = data.make;
                    vehicleMakeSelect.appendChild(newOption);
                    vehicleMakeSelect.value = data.make;
                    
                    // Add model as well
                    if (data.model) {
                        clearSelect(vehicleModelSelect, "Select Model");
                        const modelOption = document.createElement('option');
                        modelOption.value = data.model;
                        modelOption.textContent = data.model;
                        vehicleModelSelect.appendChild(modelOption);
                        vehicleModelSelect.value = data.model;
                    }
                }
            }
            
            if (data.year) {
                vehicleYearInput.value = data.year;
            }
            
            // Show success message
            lookupResult.innerHTML = `
                <strong>Vehicle found:</strong> ${data.make} ${data.model} (${data.year})
                <br>
                <small>${data.additionalInfo || ''}</small>
            `;
            lookupResult.classList.remove('d-none', 'alert-info', 'alert-danger');
            lookupResult.classList.add('alert-success');
        })
        .catch(error => {
            console.error('Error looking up vehicle:', error);
            showLookupError("Failed to lookup vehicle. Please check the registration number and try again.");
        });
    }
    
    function showLookupError(message) {
        lookupResult.textContent = message;
        lookupResult.classList.remove('d-none', 'alert-info', 'alert-success');
        lookupResult.classList.add('alert', 'alert-danger');
    }
    
    function clearSelect(selectElement, defaultText) {
        selectElement.innerHTML = '';
        const defaultOption = document.createElement('option');
        defaultOption.value = '';
        defaultOption.textContent = defaultText;
        selectElement.appendChild(defaultOption);
    }
});
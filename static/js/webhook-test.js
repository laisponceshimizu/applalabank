// Webhook Testing Interface JavaScript

document.addEventListener('DOMContentLoaded', function() {
    const jsonForm = document.getElementById('jsonForm');
    const formDataForm = document.getElementById('formDataForm');
    const responseCard = document.getElementById('responseCard');
    const responseContent = document.getElementById('responseContent');

    // Handle JSON form submission
    jsonForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const jsonData = document.getElementById('jsonData').value;
        
        try {
            // Validate JSON
            const parsedData = JSON.parse(jsonData);
            
            // Send webhook request
            await sendWebhookRequest('application/json', JSON.stringify(parsedData));
            
        } catch (error) {
            showResponse({
                status: 'error',
                message: 'Invalid JSON format',
                error: error.message
            }, 'danger');
        }
    });

    // Handle form data submission
    formDataForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const formData = new FormData(formDataForm);
        
        // Send webhook request
        await sendWebhookRequest('application/x-www-form-urlencoded', formData);
    });

    // Function to send webhook request
    async function sendWebhookRequest(contentType, data) {
        try {
            showLoading();
            
            const requestOptions = {
                method: 'POST',
                headers: {}
            };

            if (contentType === 'application/json') {
                requestOptions.headers['Content-Type'] = 'application/json';
                requestOptions.body = data;
            } else if (contentType === 'application/x-www-form-urlencoded') {
                requestOptions.body = data; // FormData automatically sets correct content-type
            }

            const response = await fetch('/webhook', requestOptions);
            const responseData = await response.json();
            
            // Determine response type based on status code
            let responseType = 'success';
            if (response.status >= 400) {
                responseType = 'danger';
            } else if (response.status >= 300) {
                responseType = 'warning';
            }
            
            showResponse(responseData, responseType, response.status);
            
        } catch (error) {
            showResponse({
                status: 'error',
                message: 'Network or server error',
                error: error.message
            }, 'danger');
        }
    }

    // Function to show loading state
    function showLoading() {
        responseCard.style.display = 'block';
        responseContent.innerHTML = `
            <div class="d-flex align-items-center">
                <div class="spinner-border spinner-border-sm me-2" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
                <span>Sending webhook request...</span>
            </div>
        `;
        responseCard.scrollIntoView({ behavior: 'smooth' });
    }

    // Function to show response
    function showResponse(data, type = 'success', statusCode = null) {
        responseCard.style.display = 'block';
        
        const statusBadge = statusCode ? `<span class="badge bg-${getStatusBadgeColor(statusCode)} me-2">${statusCode}</span>` : '';
        
        responseContent.innerHTML = `
            <div class="alert alert-${type} mb-3">
                <div class="d-flex align-items-center mb-2">
                    <i class="fas fa-${getAlertIcon(type)} me-2"></i>
                    <strong>Response Status:</strong>
                    ${statusBadge}
                    <span class="badge bg-${type === 'success' ? 'success' : 'danger'}">${data.status || 'unknown'}</span>
                </div>
                <div><strong>Message:</strong> ${data.message || 'No message'}</div>
                ${data.error ? `<div class="mt-2"><strong>Error:</strong> ${data.error}</div>` : ''}
            </div>
            
            <div class="mb-3">
                <strong>Full Response:</strong>
                <pre class="bg-dark text-light p-3 rounded mt-2"><code>${JSON.stringify(data, null, 2)}</code></pre>
            </div>
            
            <div class="text-muted small">
                <i class="fas fa-clock me-1"></i>
                Response received at: ${new Date().toLocaleString()}
            </div>
        `;
        
        responseCard.scrollIntoView({ behavior: 'smooth' });
    }

    // Helper function to get alert icon
    function getAlertIcon(type) {
        switch(type) {
            case 'success': return 'check-circle';
            case 'danger': return 'exclamation-triangle';
            case 'warning': return 'exclamation-circle';
            default: return 'info-circle';
        }
    }

    // Helper function to get status badge color
    function getStatusBadgeColor(statusCode) {
        if (statusCode >= 200 && statusCode < 300) return 'success';
        if (statusCode >= 300 && statusCode < 400) return 'warning';
        if (statusCode >= 400) return 'danger';
        return 'secondary';
    }

    // Add some example buttons for quick testing
    addQuickTestButtons();

    function addQuickTestButtons() {
        // Add quick test button for JSON
        const jsonCard = document.querySelector('#jsonForm').closest('.card');
        const jsonCardBody = jsonCard.querySelector('.card-body');
        
        const quickTestBtn = document.createElement('button');
        quickTestBtn.type = 'button';
        quickTestBtn.className = 'btn btn-outline-info btn-sm ms-2';
        quickTestBtn.innerHTML = '<i class="fas fa-bolt me-1"></i>Quick Test';
        quickTestBtn.addEventListener('click', function() {
            const sampleData = {
                "event": "quick_test",
                "timestamp": new Date().toISOString(),
                "data": {
                    "test": true,
                    "random": Math.floor(Math.random() * 1000)
                }
            };
            document.getElementById('jsonData').value = JSON.stringify(sampleData, null, 2);
        });
        
        const submitBtn = jsonCardBody.querySelector('button[type="submit"]');
        submitBtn.parentNode.appendChild(quickTestBtn);
    }
});

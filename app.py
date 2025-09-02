import os
import logging
from flask import Flask, request, jsonify, render_template
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key")

@app.route('/')
def index():
    """Serve the testing page for the webhook endpoint"""
    return render_template('index.html')

@app.route('/webhook', methods=['POST'])
def webhook():
    """
    Webhook endpoint that handles HTTP POST requests
    Accepts JSON data and returns appropriate responses
    """
    try:
        # Log the incoming request
        logger.info(f"Webhook received at {datetime.now()}")
        logger.debug(f"Request headers: {dict(request.headers)}")
        
        # Get request data
        content_type = request.content_type
        
        if content_type and 'application/json' in content_type:
            try:
                data = request.get_json()
                logger.debug(f"JSON data received: {data}")
                
                if data is None:
                    logger.warning("Invalid JSON received")
                    return jsonify({
                        'status': 'error',
                        'message': 'Invalid JSON data',
                        'timestamp': datetime.now().isoformat()
                    }), 400
                
                # Process the webhook data
                response_data = {
                    'status': 'success',
                    'message': 'Webhook received successfully',
                    'received_data': data,
                    'timestamp': datetime.now().isoformat(),
                    'data_keys': list(data.keys()) if isinstance(data, dict) else None
                }
                
                logger.info(f"Webhook processed successfully: {len(str(data))} bytes")
                return jsonify(response_data), 200
                
            except Exception as e:
                logger.error(f"Error processing JSON: {str(e)}")
                return jsonify({
                    'status': 'error',
                    'message': 'Error processing JSON data',
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                }), 400
        
        elif content_type and 'application/x-www-form-urlencoded' in content_type:
            # Handle form data
            data = request.form.to_dict()
            logger.debug(f"Form data received: {data}")
            
            response_data = {
                'status': 'success',
                'message': 'Form data webhook received successfully',
                'received_data': data,
                'timestamp': datetime.now().isoformat()
            }
            
            logger.info(f"Form webhook processed successfully")
            return jsonify(response_data), 200
        
        else:
            # Handle raw data
            raw_data = request.get_data(as_text=True)
            logger.debug(f"Raw data received: {raw_data[:200]}...")  # Log first 200 chars
            
            response_data = {
                'status': 'success',
                'message': 'Raw data webhook received successfully',
                'received_data': raw_data,
                'content_type': content_type,
                'data_length': len(raw_data),
                'timestamp': datetime.now().isoformat()
            }
            
            logger.info(f"Raw webhook processed successfully: {len(raw_data)} bytes")
            return jsonify(response_data), 200
            
    except Exception as e:
        logger.error(f"Unexpected error in webhook: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'Internal server error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/webhook', methods=['GET'])
def webhook_info():
    """
    GET endpoint for webhook information
    """
    return jsonify({
        'endpoint': '/webhook',
        'method': 'POST',
        'description': 'Webhook endpoint for receiving HTTP POST requests',
        'supported_content_types': [
            'application/json',
            'application/x-www-form-urlencoded',
            'text/plain'
        ],
        'timestamp': datetime.now().isoformat()
    }), 200

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({
        'status': 'error',
        'message': 'Endpoint not found',
        'timestamp': datetime.now().isoformat()
    }), 404

@app.errorhandler(405)
def method_not_allowed(error):
    """Handle 405 errors (Method Not Allowed)"""
    return jsonify({
        'status': 'error',
        'message': 'Method not allowed for this endpoint',
        'allowed_methods': ['POST'] if request.endpoint == 'webhook' else [],
        'timestamp': datetime.now().isoformat()
    }), 405

if __name__ == '__main__':
    logger.info("Starting Flask webhook server...")
    app.run(host='0.0.0.0', port=5000, debug=True)

from app import create_app
import os
import socket

def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

app = create_app()

if __name__ == '__main__':
    if 'PORT' in os.environ:
        port = int(os.environ['PORT'])
    elif os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        port = int(os.environ.get('ACTIVE_PORT', 5000))
    else:
        port = 5001 if is_port_in_use(5000) else 5000
        os.environ['ACTIVE_PORT'] = str(port)

    print(f"Starting GreenCycle Nexus on port {port}...")
    app.run(debug=True, host='0.0.0.0', port=port)

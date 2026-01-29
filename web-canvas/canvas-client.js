// Written by Perplexity.AI sometime in 2025

class RemoteCanvas {
  constructor() {
    this.canvas = document.getElementById('remoteCanvas');
    this.ctx = this.canvas.getContext('2d');
    this.socket = new WebSocket('ws://localhost:4000');

    this.setupSocketListeners();
    this.setupCanvasListeners();
  }

  setupSocketListeners() {
    this.socket.addEventListener('open', () => {
      console.log('Connected to WebSocket server');
    });

    this.socket.addEventListener('message', (event) => {
      const drawCommand = JSON.parse(event.data);
      this.executeDrawCommand(drawCommand);
    });
  }

  setupCanvasListeners() {
    const events = ['mousedown', /*'mousemove',*/ 'mouseup', /*'mouseout'*/];
    events.forEach(eventType => {
      this.canvas.addEventListener(eventType, (e) => {
        const eventData = {
          type: eventType,
          x: e.offsetX,
          y: e.offsetY,
          buttons: e.buttons
        };
        this.socket.send(JSON.stringify(eventData));
      });
    });
  }

  executeDrawCommand(command) {
    switch(command.method) {
      case 'beginPath':
        this.ctx.beginPath();
        break;
      case 'moveTo':
        this.ctx.moveTo(...command.value);
        break;
      case 'lineTo':
        this.ctx.lineTo(...command.value);
        break;
      case 'stroke':
        this.ctx.stroke();
        break;
      case 'lineWidth':
        this.ctx.lineWidth = command.value;
        break;
      case 'strokeStyle':
        this.ctx.strokeStyle = toStyle(command.value);
        break;
      case 'fillStyle':
        this.ctx.fillStyle = toStyle(command.value);
        break;
      case 'fillRect':
        this.ctx.fillRect(...command.params);
        break;
    }
  }
}

toStyle = n => '#'+n.toString(16).padStart(6, '0');

canvas = new RemoteCanvas();

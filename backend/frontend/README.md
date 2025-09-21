# 🏠 Rental Agreement AI - Frontend Dashboard

A beautiful, modern dashboard for managing rental agreements with AI-powered analysis and chat assistance.

![Dashboard Preview](preview.png)

## ✨ Features

- **🏢 Dashboard**: Overview with statistics and recent agreements
- **📄 Agreement Management**: Upload, view, and organize rental agreements
- **🤖 AI Chat Assistant**: Ask questions about your rental agreements
- **🔔 Alerts & Notifications**: Stay updated on important lease information
- **⚙️ Settings**: Configure user preferences and API endpoints
- **📱 Responsive Design**: Works on desktop, tablet, and mobile

## 🚀 Quick Start

### Prerequisites
- Your backend server running on `http://127.0.0.1:8001`
- Modern web browser (Chrome, Firefox, Safari, Edge)

### Setup

1. **Clone/Download the frontend files**
   ```
   frontend/
   ├── index.html
   ├── styles.css
   ├── script.js
   └── README.md
   ```

2. **Start the backend server** (if not already running)
   ```bash
   cd ../backend
   python start_server.py
   ```

3. **Open the frontend**
   - Double-click `index.html` to open in browser
   - Or use a local server:
   ```bash
   # Using Python (if available)
   python -m http.server 3000
   # Or using Node.js
   npx serve .
   ```

4. **Access the dashboard**
   - Open: http://localhost:3000 (if using local server)
   - Or directly open `index.html` in browser

## 📋 Usage Guide

### 🏢 Dashboard
- View statistics: Total agreements, active contracts, expiring leases
- Quick upload area for new rental agreements
- Recent agreements table with clickable rows for details

### 📄 Upload Documents
1. **Drag & Drop**: Drag PDF files onto the upload area
2. **Browse**: Click "Browse Files" to select documents
3. **Processing**: Watch the progress bar as AI processes your document
4. **Results**: View extracted information and AI summary

### 🤖 AI Chat
- Ask questions like:
  - "What is my rent amount?"
  - "When is rent due?"
  - "Who is my landlord?"
  - "What are the lease terms?"
  - "Are pets allowed?"

### 📊 Agreements Page
- Grid view of all uploaded agreements
- Click any card to view detailed information
- Status indicators (Active, Expiring Soon, Expired)

### 🔔 Alerts
- Lease expiration warnings
- Rent due reminders
- Document processing notifications
- System alerts

### ⚙️ Settings
- **User ID**: Set your unique identifier
- **API URL**: Configure backend server URL
- **System Status**: Monitor backend and AI service health

## 🎨 Design Features

### Color Scheme
- **Dark Theme**: Modern dark blue/gray palette
- **Accent Colors**: 
  - Primary: Blue (#4c6ef5)
  - Success: Green (#48bb78)
  - Warning: Orange (#ed8936)
  - Error: Red (#e53e3e)

### Components
- **Gradient Cards**: Beautiful stat cards with hover effects
- **Smooth Animations**: Fade-ins, slide-ups, and transitions
- **Interactive Elements**: Buttons, modals, drag-and-drop
- **Status Indicators**: Color-coded badges for agreement status

### Responsive Layout
- **Desktop**: Full sidebar + main content area
- **Tablet**: Compressed sidebar
- **Mobile**: Collapsible sidebar menu

## 🔧 Configuration

### API Configuration
The frontend automatically connects to your backend server. Default settings:

```javascript
const CONFIG = {
    API_BASE_URL: 'http://127.0.0.1:8001',
    USER_ID: 'auto-generated',
    MAX_FILE_SIZE: 10 * 1024 * 1024, // 10MB
    ALLOWED_FILE_TYPES: ['application/pdf', 'text/plain', ...]
};
```

### Customization
- **Colors**: Edit CSS variables in `styles.css`
- **API Endpoints**: Modify `CONFIG` object in `script.js`
- **Mock Data**: Update `generateMockAgreements()` for demo content

## 📡 Backend Integration

### API Endpoints Used
- `GET /health` - System health check
- `POST /upload-document/` - Upload rental agreements
- `POST /query-agent/` - AI chat queries

### Required Headers
- `X-User-ID` - Automatically included in all requests

## 🛠️ Development

### File Structure
```
frontend/
├── index.html          # Main HTML structure
├── styles.css          # All styling (dark theme)
├── script.js           # JavaScript functionality
└── README.md           # This file
```

### Key JavaScript Functions
- `uploadDocument()` - Handles file uploads
- `queryAgent()` - Sends chat messages to AI
- `updateStats()` - Updates dashboard statistics
- `showPage()` - Navigation between sections
- `showAgreementDetails()` - Modal for agreement details

### Styling Architecture
- **CSS Grid & Flexbox** for layouts
- **CSS Custom Properties** for consistent theming
- **CSS Animations** for smooth interactions
- **Responsive Design** with media queries

## 🐛 Troubleshooting

### Backend Connection Issues
1. Ensure backend server is running on port 8001
2. Check Settings page for system status
3. Verify API URL in settings matches backend

### File Upload Problems
- Only PDF files are fully supported
- File size limit: 10MB
- Check browser console for error messages

### Chat Not Working
- Ensure backend AI services are running
- Check network connection
- Try refreshing the page

### Styling Issues
- Hard refresh (Ctrl+F5) to clear cache
- Check browser compatibility
- Ensure all CSS files loaded properly

## 🌟 Features in Detail

### Dashboard Statistics
- **Total Agreements**: Count of all uploaded documents
- **Active Contracts**: Currently valid lease agreements
- **Expiring Soon**: Leases ending within 60 days
- **Alerts**: System notifications and reminders

### File Processing Flow
1. **Upload**: Drag/drop or browse file selection
2. **Validation**: File type and size checks
3. **Progress**: Visual upload progress indicator
4. **AI Processing**: Document AI extraction and analysis
5. **Storage**: Secure database storage with embeddings
6. **Display**: Updated dashboard with new agreement

### AI Chat Capabilities
- **Context Aware**: Knows about your specific agreements
- **Natural Language**: Ask questions in plain English
- **Real-time**: Instant responses from AI backend
- **Persistent**: Chat history maintained during session
- **Error Handling**: Graceful error messages and retry options

## 📱 Mobile Experience

- **Touch-Friendly**: Large buttons and touch targets
- **Responsive Tables**: Horizontal scrolling for data tables
- **Collapsible Sidebar**: Space-efficient navigation
- **Optimized Modals**: Full-screen dialogs on small devices

## 🔒 Security & Privacy

- **User Isolation**: Each user sees only their own data
- **Secure Headers**: X-User-ID for request authentication
- **Local Storage**: Settings saved locally in browser
- **CORS Enabled**: Secure cross-origin requests

## 🎯 Best Practices

### For Users
1. Use clear, descriptive filenames for uploads
2. Upload complete, legible documents
3. Ask specific questions in AI chat
4. Regularly check alerts for important updates

### For Developers
1. Follow existing code structure and naming
2. Test on multiple browsers and devices
3. Validate all user inputs
4. Handle errors gracefully with user feedback

---

## 🚀 Ready to Use!

Your Rental Agreement AI Dashboard is ready to help manage rental agreements with the power of AI! 

**Start by:**
1. Opening `index.html` in your browser
2. Uploading your first rental agreement
3. Exploring the AI chat assistant
4. Configuring settings as needed

**Need help?** Check the troubleshooting section above or review the browser console for technical details.

---

Built with ❤️ for smarter rental management

// Global configuration
const CONFIG = {
    API_BASE_URL: '/api',
    USER_ID: null, // Will be set by user input
    MAX_FILE_SIZE: 10 * 1024 * 1024, // 10MB
    ALLOWED_FILE_TYPES: ['application/pdf', 'text/plain', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']
};

// Application state
let appState = {
    userLoggedIn: false,
    agreements: [],
    currentPage: 'dashboard',
    currentSummary: null,
    currentReminders: []
};

// Utility functions
const formatDate = (dateString) => {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', { 
        year: 'numeric', 
        month: 'short', 
        day: 'numeric' 
    });
};

const formatCurrency = (amount) => {
    if (!amount || amount === 'N/A') return 'N/A';
    // Extract numbers from string if it contains currency symbols
    const numericAmount = parseFloat(amount.toString().replace(/[^0-9.-]+/g, ''));
    if (isNaN(numericAmount)) return amount;
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD'
    }).format(numericAmount);
};

const showNotification = (message, type = 'info') => {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <span>${message}</span>
        <button onclick="this.parentElement.remove()">×</button>
    `;
    
    // Add to page (create container if needed)
    let container = document.querySelector('.notification-container');
    if (!container) {
        container = document.createElement('div');
        container.className = 'notification-container';
        document.body.appendChild(container);
    }
    
    container.appendChild(notification);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (notification.parentElement) {
            notification.remove();
        }
    }, 5000);
};

// API functions
const apiCall = async (endpoint, options = {}) => {
    const url = `${CONFIG.API_BASE_URL}${endpoint}`;
    const defaultOptions = {
        headers: {
            'X-User-ID': CONFIG.USER_ID,
            ...options.headers
        }
    };

    try {
        const response = await fetch(url, { ...defaultOptions, ...options });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const contentType = response.headers.get('content-type');
        if (contentType && contentType.includes('application/json')) {
            return await response.json();
        }
        
        return await response.text();
    } catch (error) {
        console.error(`API call failed for ${endpoint}:`, error);
        throw error;
    }
};

// Backend API functions
const checkBackendHealth = async () => {
    try {
        const health = await apiCall('/health');
        updateSystemStatus('backend-status', 'Healthy', 'healthy');
        updateSystemStatus('ai-status', health.services?.gemini_ai || 'Available', 'healthy');
        return health;
    } catch (error) {
        updateSystemStatus('backend-status', 'Error', 'error');
        updateSystemStatus('ai-status', 'Unavailable', 'error');
        throw error;
    }
};

const uploadDocument = async (file) => {
    const formData = new FormData();
    formData.append('file', file);

    return await apiCall('/upload-document/', {
        method: 'POST',
        body: formData
    });
};

const queryAgent = async (query) => {
    const params = new URLSearchParams({ query });
    return await apiCall(`/query-agent/?${params}`, {
        method: 'POST'
    });
};

// User Management Functions
const setUserId = () => {
    const input = document.getElementById('user-id-main');
    const userId = input.value.trim();
    
    if (!userId) {
        showNotification('Please enter a valid User ID', 'error');
        return;
    }
    
    if (userId.length < 3) {
        showNotification('User ID must be at least 3 characters long', 'error');
        return;
    }
    
    // Set user ID
    CONFIG.USER_ID = userId;
    appState.userLoggedIn = true;
    
    // Save to localStorage
    localStorage.setItem('rental-ai-user-id', userId);
    
    // Update UI
    document.getElementById('current-user-display').textContent = userId;
    
    // Show upload section and hide user section
    document.getElementById('user-section').style.display = 'none';
    document.getElementById('upload-section').style.display = 'block';
    document.getElementById('info-section').style.display = 'block';
    
    // Update stats
    updateStats();
    updateRecentAgreements();
    
    showNotification(`Welcome, ${userId}! You can now upload documents.`, 'success');
};

const changeUser = () => {
    // Reset state
    CONFIG.USER_ID = null;
    appState.userLoggedIn = false;
    appState.agreements = [];
    appState.currentSummary = null;
    appState.currentReminders = [];
    
    // Clear localStorage
    localStorage.removeItem('rental-ai-user-id');
    
    // Reset UI
    document.getElementById('user-id-main').value = '';
    document.getElementById('current-user-display').textContent = 'Not set';
    
    // Show user section and hide others
    document.getElementById('user-section').style.display = 'block';
    document.getElementById('upload-section').style.display = 'none';
    document.getElementById('info-section').style.display = 'none';
    
    // Clear summary and reminders
    document.getElementById('document-summary').innerHTML = '<p class="no-data">Upload a document to see the AI-generated summary</p>';
    document.getElementById('document-reminders').innerHTML = '<p class="no-data">Upload a document to see important dates and reminders</p>';
    
    // Reset stats
    updateStats();
    updateRecentAgreements();
    
    showNotification('User changed. Please enter your User ID.', 'info');
};

const loadSavedUser = () => {
    const savedUserId = localStorage.getItem('rental-ai-user-id');
    
    if (savedUserId) {
        document.getElementById('user-id-main').value = savedUserId;
        CONFIG.USER_ID = savedUserId;
        appState.userLoggedIn = true;
        
        // Update UI immediately
        document.getElementById('current-user-display').textContent = savedUserId;
        document.getElementById('user-section').style.display = 'none';
        document.getElementById('upload-section').style.display = 'block';
        document.getElementById('info-section').style.display = 'block';
        
        console.log('Loaded saved user:', savedUserId);
    }
};

// UI Update functions
const updateStats = () => {
    const agreements = appState.agreements;
    const totalAgreements = agreements.length;
    const activeContracts = agreements.filter(a => a.status === 'Active').length;
    const expiringSoon = agreements.filter(a => a.status === 'Expiring Soon').length;
    const totalAlerts = appState.currentReminders.length;

    document.getElementById('total-agreements').textContent = totalAgreements;
    document.getElementById('active-contracts').textContent = activeContracts;
    document.getElementById('expiring-soon').textContent = expiringSoon;
    document.getElementById('total-alerts').textContent = totalAlerts;
};

const updateSystemStatus = (elementId, text, status) => {
    const element = document.getElementById(elementId);
    if (element) {
        element.textContent = text;
        element.className = `status-indicator status-${status}`;
    }
};

const updateRecentAgreements = () => {
    const tbody = document.getElementById('recent-agreements');
    
    if (!appState.userLoggedIn) {
        tbody.innerHTML = `
            <tr>
                <td colspan="5" class="text-center">
                    <p>Please enter your User ID to view your agreements.</p>
                </td>
            </tr>
        `;
        return;
    }
    
    const agreements = appState.agreements.slice(0, 5); // Show only recent 5

    if (agreements.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="5" class="text-center">
                    <p>No agreements found for user: <strong>${CONFIG.USER_ID}</strong></p>
                    <p style="font-size: 14px; color: #a0aec0; margin-top: 8px;">
                        Upload your first rental agreement to get started.
                    </p>
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = agreements.map(agreement => `
        <tr onclick="showAgreementDetails('${agreement.id}')">
            <td>${formatDate(agreement.date)}</td>
            <td>
                <div style="display: flex; align-items: center; gap: 8px;">
                    <i class="fas fa-file-pdf" style="color: #e53e3e;"></i>
                    ${agreement.filename}
                </div>
            </td>
            <td>${agreement.parties}</td>
            <td>${agreement.rent}</td>
            <td>
                <span class="status-badge ${agreement.status === 'Active' ? 'status-complete' : 
                    agreement.status === 'Expiring Soon' ? 'status-pending' : 'status-expired'}">
                    ${agreement.status}
                </span>
            </td>
        </tr>
    `).join('');
};

const updateAgreementsPage = () => {
    const container = document.getElementById('agreements-grid');
    const agreements = appState.agreements;

    if (agreements.length === 0) {
        container.innerHTML = `
            <div class="loading-message">
                <i class="fas fa-file-contract" style="font-size: 48px; color: #4c6ef5; margin-bottom: 16px;"></i>
                <p>No agreements uploaded yet.</p>
                <p style="color: #a0aec0; font-size: 14px;">Upload your first rental agreement to get started.</p>
                <button class="btn btn-primary mt-4" onclick="showPage('dashboard')">
                    <i class="fas fa-upload"></i> Upload Agreement
                </button>
            </div>
        `;
        return;
    }

    container.innerHTML = agreements.map(agreement => `
        <div class="agreement-card" onclick="showAgreementDetails('${agreement.id}')">
            <h3>${agreement.filename}</h3>
            <p>Uploaded on ${formatDate(agreement.date)}</p>
            <div class="agreement-details">
                <div class="detail-row">
                    <span class="detail-label">Tenant:</span>
                    <span class="detail-value">${agreement.structured_info?.tenant_name || 'N/A'}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Rent:</span>
                    <span class="detail-value">${formatCurrency(agreement.structured_info?.rent_amount)}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Due Date:</span>
                    <span class="detail-value">${agreement.structured_info?.due_date || 'N/A'}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Status:</span>
                    <span class="status-badge ${agreement.status === 'Active' ? 'status-complete' : 
                        agreement.status === 'Expiring Soon' ? 'status-pending' : 'status-expired'}">
                        ${agreement.status}
                    </span>
                </div>
            </div>
        </div>
    `).join('');
};

// Summary and Reminder Display Functions
const displayDocumentSummary = (summary) => {
    const summaryElement = document.getElementById('document-summary');
    
    if (!summary) {
        summaryElement.innerHTML = '<p class="no-data">Upload a document to see the AI-generated summary</p>';
        return;
    }
    
    appState.currentSummary = summary;
    summaryElement.innerHTML = `
        <div class="summary-content">
            <p>${summary}</p>
        </div>
    `;
};

const displayDocumentReminders = (structuredInfo) => {
    const remindersElement = document.getElementById('document-reminders');
    
    if (!structuredInfo) {
        remindersElement.innerHTML = '<p class="no-data">Upload a document to see important dates and reminders</p>';
        return;
    }
    
    const reminders = [];
    
    // Create reminders based on structured info
    if (structuredInfo.due_date && structuredInfo.due_date !== 'N/A') {
        reminders.push({
            type: 'rent',
            title: 'Rent Due Date',
            description: `Your rent is due on the ${structuredInfo.due_date} of each month`,
            date: structuredInfo.due_date
        });
    }
    
    if (structuredInfo.rent_amount && structuredInfo.rent_amount !== 'N/A') {
        reminders.push({
            type: 'amount',
            title: 'Monthly Rent Amount',
            description: `Your monthly rent is ${formatCurrency(structuredInfo.rent_amount)}`,
            date: 'Monthly'
        });
    }
    
    if (structuredInfo.duration && structuredInfo.duration !== 'N/A') {
        reminders.push({
            type: 'lease',
            title: 'Lease Duration',
            description: `Your lease term: ${structuredInfo.duration}`,
            date: 'Check lease end date'
        });
    }
    
    if (structuredInfo.security_deposit_amount && structuredInfo.security_deposit_amount !== 'N/A') {
        reminders.push({
            type: 'deposit',
            title: 'Security Deposit',
            description: `Security deposit paid: ${formatCurrency(structuredInfo.security_deposit_amount)}`,
            date: 'Refundable at lease end'
        });
    }
    
    appState.currentReminders = reminders;
    
    if (reminders.length === 0) {
        remindersElement.innerHTML = '<p class="no-data">No specific reminders found in this document</p>';
        return;
    }
    
    remindersElement.innerHTML = reminders.map(reminder => `
        <div class="reminder-item">
            <div class="reminder-date">${reminder.date}</div>
            <div class="reminder-title">${reminder.title}</div>
            <div class="reminder-description">${reminder.description}</div>
        </div>
    `).join('');
};

const updateAlertsPage = () => {
    const container = document.getElementById('alerts-container');
    
    if (!appState.userLoggedIn) {
        container.innerHTML = `
            <div class="loading-message">
                <i class="fas fa-user-lock" style="font-size: 48px; color: #4c6ef5; margin-bottom: 16px;"></i>
                <p>Please log in to view alerts.</p>
            </div>
        `;
        return;
    }
    
    const reminders = appState.currentReminders;

    if (reminders.length === 0) {
        container.innerHTML = `
            <div class="loading-message">
                <i class="fas fa-bell-slash" style="font-size: 48px; color: #4c6ef5; margin-bottom: 16px;"></i>
                <p>No alerts at this time.</p>
                <p style="color: #a0aec0; font-size: 14px;">Upload documents to see important reminders and dates.</p>
            </div>
        `;
        return;
    }

    container.innerHTML = reminders.map(reminder => `
        <div class="alert-item">
            <div class="alert-icon alert-info">
                <i class="fas fa-bell"></i>
            </div>
            <div class="alert-content">
                <div class="alert-title">${reminder.title}</div>
                <div class="alert-description">${reminder.description}</div>
                <div class="alert-time">${reminder.date}</div>
            </div>
        </div>
    `).join('');
};

// Navigation functions
const showPage = (pageId) => {
    // Update nav items
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.remove('active');
        if (item.dataset.page === pageId) {
            item.classList.add('active');
        }
    });

    // Update pages
    document.querySelectorAll('.page').forEach(page => {
        page.classList.remove('active');
    });
    
    const targetPage = document.getElementById(`${pageId}-page`);
    if (targetPage) {
        targetPage.classList.add('active');
        targetPage.classList.add('fade-in');
    }

    // Update page title
    const titles = {
        dashboard: 'Rental Assistant',
        agreements: 'All Agreements',
        alerts: 'Alerts & Notifications',
        chatbot: 'AI Assistant',
        settings: 'Settings'
    };
    
    document.getElementById('page-title').textContent = titles[pageId] || 'Rental Assistant';
    appState.currentPage = pageId;

    // Load page-specific data
    if (pageId === 'agreements') {
        updateAgreementsPage();
    } else if (pageId === 'alerts') {
        updateAlertsPage();
    }
};

// Modal functions
const showAgreementDetails = (agreementId) => {
    const agreement = appState.agreements.find(a => a.id === agreementId);
    if (!agreement) return;

    const modal = document.getElementById('agreement-modal');
    const title = document.getElementById('modal-title');
    const body = document.getElementById('modal-body');

    title.textContent = agreement.filename;
    
    body.innerHTML = `
        <div class="agreement-details">
            <div class="detail-row mb-4">
                <span class="detail-label">Upload Date:</span>
                <span class="detail-value">${formatDate(agreement.date)}</span>
            </div>
            <div class="detail-row mb-4">
                <span class="detail-label">Parties:</span>
                <span class="detail-value">${agreement.parties}</span>
            </div>
            <div class="detail-row mb-4">
                <span class="detail-label">Status:</span>
                <span class="status-badge ${agreement.status === 'Active' ? 'status-complete' : 
                    agreement.status === 'Expiring Soon' ? 'status-pending' : 'status-expired'}">
                    ${agreement.status}
                </span>
            </div>
            
            <h4 style="color: #ffffff; margin: 24px 0 16px 0;">Agreement Details</h4>
            <div class="setting-group">
                <div class="detail-row mb-4">
                    <span class="detail-label">Tenant Name:</span>
                    <span class="detail-value">${agreement.structured_info?.tenant_name || 'N/A'}</span>
                </div>
                <div class="detail-row mb-4">
                    <span class="detail-label">Landlord:</span>
                    <span class="detail-value">${agreement.structured_info?.landlord_name || 'N/A'}</span>
                </div>
                <div class="detail-row mb-4">
                    <span class="detail-label">Property Address:</span>
                    <span class="detail-value">${agreement.structured_info?.property_address || 'N/A'}</span>
                </div>
                <div class="detail-row mb-4">
                    <span class="detail-label">Monthly Rent:</span>
                    <span class="detail-value">${formatCurrency(agreement.structured_info?.rent_amount)}</span>
                </div>
                <div class="detail-row mb-4">
                    <span class="detail-label">Due Date:</span>
                    <span class="detail-value">${agreement.structured_info?.due_date || 'N/A'}</span>
                </div>
                <div class="detail-row mb-4">
                    <span class="detail-label">Lease Duration:</span>
                    <span class="detail-value">${agreement.structured_info?.duration || 'N/A'}</span>
                </div>
            </div>
            
            <div style="margin-top: 24px;">
                <button class="btn btn-primary" onclick="showPage('chatbot'); closeModal();">
                    <i class="fas fa-comments"></i> Ask AI about this agreement
                </button>
            </div>
        </div>
    `;

    modal.classList.add('active');
};

const closeModal = () => {
    document.getElementById('agreement-modal').classList.remove('active');
};

// File upload functions
const setupFileUpload = () => {
    const uploadArea = document.getElementById('upload-area');
    const fileInput = document.getElementById('file-input');

    // Drag and drop events
    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('dragover');
    });

    uploadArea.addEventListener('dragleave', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('dragover');
    });

    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('dragover');
        
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleFileUpload(files[0]);
        }
    });

    // File input change
    fileInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) {
            handleFileUpload(file);
        }
    });

    // Click to upload
    uploadArea.addEventListener('click', () => {
        fileInput.click();
    });
};

const handleFileUpload = async (file) => {
    // Check if user is logged in
    if (!appState.userLoggedIn || !CONFIG.USER_ID) {
        showNotification('Please enter your User ID before uploading documents', 'error');
        return;
    }
    
    // Validate file
    if (file.size > CONFIG.MAX_FILE_SIZE) {
        showNotification('File size exceeds 10MB limit', 'error');
        return;
    }

    if (!CONFIG.ALLOWED_FILE_TYPES.includes(file.type)) {
        showNotification('Invalid file type. Please upload PDF, DOC, DOCX, or TXT files.', 'error');
        return;
    }

    // Show upload progress
    const uploadContent = document.querySelector('.upload-content');
    const uploadProgress = document.getElementById('upload-progress');
    const progressFill = document.getElementById('progress-fill');
    const progressText = document.getElementById('progress-text');

    uploadContent.style.display = 'none';
    uploadProgress.style.display = 'block';

    try {
        console.log(`Uploading file for user: ${CONFIG.USER_ID}`);
        
        // Simulate progress for better UX
        let progress = 0;
        const progressInterval = setInterval(() => {
            progress += Math.random() * 20;
            if (progress > 85) progress = 85;
            progressFill.style.width = `${progress}%`;
            progressText.textContent = 'Processing with AI...';
        }, 800);

        // Upload file
        const result = await uploadDocument(file);
        
        console.log('Upload result:', result);

        // Complete progress
        clearInterval(progressInterval);
        progressFill.style.width = '100%';
        progressText.textContent = 'Analysis complete!';

        // Add to agreements list
        const newAgreement = {
            id: Date.now().toString(),
            filename: file.name,
            date: new Date().toISOString(),
            parties: `${result.structured_info?.tenant_name || 'Unknown'} & ${result.structured_info?.landlord_name || 'Unknown'}`,
            rent: formatCurrency(result.structured_info?.rent_amount) || 'N/A',
            status: 'Active',
            structured_info: result.structured_info,
            summary: result.summary
        };

        appState.agreements.unshift(newAgreement);

        // Display summary and reminders automatically
        displayDocumentSummary(result.summary);
        displayDocumentReminders(result.structured_info);

        // Update UI
        updateStats();
        updateRecentAgreements();

        showNotification(`Successfully processed ${file.name} for ${CONFIG.USER_ID}!`, 'success');

    } catch (error) {
        console.error('Upload failed:', error);
        showNotification(`Upload failed: ${error.message}`, 'error');
    } finally {
        // Reset upload UI after delay
        setTimeout(() => {
            uploadContent.style.display = 'block';
            uploadProgress.style.display = 'none';
            progressFill.style.width = '0%';
            document.getElementById('file-input').value = '';
        }, 3000);
    }
};

// Chat functions
const sendMessage = async () => {
    const input = document.getElementById('chat-input');
    const sendButton = document.getElementById('send-button');
    const message = input.value.trim();

    if (!message) return;

    // Disable input
    input.disabled = true;
    sendButton.disabled = true;

    // Add user message to chat
    addChatMessage(message, 'user');
    
    // Clear input
    input.value = '';

    try {
        // Show typing indicator
        const typingId = addTypingIndicator();

        // Send to AI
        const response = await queryAgent(message);
        
        // Remove typing indicator
        removeTypingIndicator(typingId);

        // Add AI response
        addChatMessage(response.response, 'bot');

    } catch (error) {
        removeTypingIndicator();
        addChatMessage('Sorry, I encountered an error processing your question. Please try again.', 'bot');
        showNotification('Failed to get AI response', 'error');
    } finally {
        // Re-enable input
        input.disabled = false;
        sendButton.disabled = false;
        input.focus();
    }
};

const addChatMessage = (content, type) => {
    const messagesContainer = document.getElementById('chat-messages');
    const messageDiv = document.createElement('div');
    
    messageDiv.className = `message ${type}-message fade-in`;
    messageDiv.innerHTML = `
        <div class="message-avatar">
            <i class="fas fa-${type === 'user' ? 'user' : 'robot'}"></i>
        </div>
        <div class="message-content">
            <p>${content}</p>
            <span class="message-time">${new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</span>
        </div>
    `;

    messagesContainer.appendChild(messageDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
};

let typingIndicatorId = 0;

const addTypingIndicator = () => {
    const messagesContainer = document.getElementById('chat-messages');
    const typingDiv = document.createElement('div');
    
    typingIndicatorId++;
    const currentId = typingIndicatorId;
    
    typingDiv.id = `typing-${currentId}`;
    typingDiv.className = 'message bot-message';
    typingDiv.innerHTML = `
        <div class="message-avatar">
            <i class="fas fa-robot"></i>
        </div>
        <div class="message-content">
            <div class="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
            </div>
        </div>
    `;

    messagesContainer.appendChild(typingDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
    
    return currentId;
};

const removeTypingIndicator = (id) => {
    const typingElement = document.getElementById(`typing-${id || typingIndicatorId}`);
    if (typingElement) {
        typingElement.remove();
    }
};

// Settings functions for the settings page
const saveUserId = () => {
    const input = document.getElementById('user-id-input');
    const newUserId = input.value.trim();
    
    if (newUserId && newUserId !== CONFIG.USER_ID) {
        // This will change the current user
        CONFIG.USER_ID = newUserId;
        localStorage.setItem('rental-ai-user-id', newUserId);
        
        // Update UI
        document.getElementById('current-user-display').textContent = newUserId;
        document.getElementById('user-id-main').value = newUserId;
        
        // Reset agreements since user changed
        appState.agreements = [];
        appState.currentSummary = null;
        appState.currentReminders = [];
        
        updateStats();
        updateRecentAgreements();
        
        showNotification(`User ID updated to: ${newUserId}`, 'success');
    }
};

const saveApiUrl = () => {
    const input = document.getElementById('api-url-input');
    const newUrl = input.value.trim();
    
    if (newUrl && newUrl !== CONFIG.API_BASE_URL) {
        CONFIG.API_BASE_URL = newUrl;
        localStorage.setItem('rental-ai-api-url', newUrl);
        showNotification('API URL saved successfully', 'success');
        
        // Re-check backend health with new URL
        checkBackendHealth().catch(() => {
            showNotification('Warning: Cannot connect to new API URL', 'warning');
        });
    }
};

// Event listeners
document.addEventListener('DOMContentLoaded', () => {
    // Load saved user if available
    loadSavedUser();
    
    // Setup file upload
    setupFileUpload();
    
    // Setup navigation
    document.querySelectorAll('.nav-item[data-page]').forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            showPage(item.dataset.page);
        });
    });

    // Setup chat input
    document.getElementById('chat-input').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            sendMessage();
        }
    });

    // Setup user input enter key
    document.getElementById('user-id-main').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            setUserId();
        }
    });

    // Setup modal close on outside click
    document.getElementById('agreement-modal').addEventListener('click', (e) => {
        if (e.target === e.currentTarget) {
            closeModal();
        }
    });

    // Initialize UI
    updateStats();
    updateRecentAgreements();
    
    // Load settings in settings page inputs
    const savedApiUrl = localStorage.getItem('rental-ai-api-url');
    if (savedApiUrl) {
        CONFIG.API_BASE_URL = savedApiUrl;
    }
    
    // Set settings page values
    if (document.getElementById('user-id-input')) {
        document.getElementById('user-id-input').value = CONFIG.USER_ID || '';
    }
    if (document.getElementById('api-url-input')) {
        document.getElementById('api-url-input').value = CONFIG.API_BASE_URL;
    }

    // Check backend health
    checkBackendHealth().catch(() => {
        showNotification('Backend connection failed. Some features may not work.', 'warning');
    });

    console.log('🏠 Rental Agreement AI Frontend initialized');
    console.log('📊 User ID:', CONFIG.USER_ID || 'Not set');
    console.log('🔗 API URL:', CONFIG.API_BASE_URL);
});

// Add CSS for typing indicator and notifications
const additionalCSS = `
.typing-indicator {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 8px 0;
}

.typing-indicator span {
    height: 6px;
    width: 6px;
    background-color: #a0aec0;
    border-radius: 50%;
    animation: typing 1.4s infinite ease-in-out;
}

.typing-indicator span:nth-child(2) {
    animation-delay: 0.2s;
}

.typing-indicator span:nth-child(3) {
    animation-delay: 0.4s;
}

@keyframes typing {
    0%, 60%, 100% {
        opacity: 0.3;
        transform: translateY(0);
    }
    30% {
        opacity: 1;
        transform: translateY(-4px);
    }
}

.notification-container {
    position: fixed;
    top: 20px;
    right: 20px;
    z-index: 2000;
    display: flex;
    flex-direction: column;
    gap: 12px;
    max-width: 400px;
}

.notification {
    background: linear-gradient(135deg, #1a1f2e 0%, #2d3748 100%);
    border-radius: 8px;
    padding: 16px;
    border-left: 4px solid #4c6ef5;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
    display: flex;
    justify-content: space-between;
    align-items: center;
    animation: slideInRight 0.3s ease-out;
}

.notification-success {
    border-left-color: #48bb78;
}

.notification-error {
    border-left-color: #e53e3e;
}

.notification-warning {
    border-left-color: #ed8936;
}

.notification button {
    background: none;
    border: none;
    color: #a0aec0;
    cursor: pointer;
    font-size: 18px;
    padding: 4px;
    margin-left: 12px;
}

@keyframes slideInRight {
    from {
        transform: translateX(100%);
        opacity: 0;
    }
    to {
        transform: translateX(0);
        opacity: 1;
    }
}
`;

// Add the additional CSS to the page
const styleSheet = document.createElement('style');
styleSheet.textContent = additionalCSS;
document.head.appendChild(styleSheet);

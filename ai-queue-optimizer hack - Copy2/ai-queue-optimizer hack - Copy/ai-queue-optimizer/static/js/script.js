// Global utility functions
class QueueUI {
    static updateProgressCircle(percentage) {
        const circle = document.querySelector('.progress-circle-fill');
        if (circle) {
            const circumference = 314; // 2 * π * r (r = 50)
            const offset = circumference - (percentage / 100) * circumference;
            circle.style.strokeDashoffset = offset;
        }
    }

    static updateQueueStats() {
        fetch('/api/queue-stats')
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(stats => {
                // Update stats on dashboard
                document.querySelectorAll('[data-stat]').forEach(el => {
                    const stat = el.dataset.stat;
                    if (stats[stat] !== undefined) {
                        if (stat === 'average_wait_time') {
                            el.textContent = this.formatTime(stats[stat]);
                        } else if (stat === 'is_rush_hour') {
                            el.textContent = stats[stat] ? 'Yes' : 'No';
                        } else {
                            el.textContent = stats[stat];
                        }
                    }
                });

                // Update progress circle if on user dashboard
                if (window.location.pathname.includes('dashboard')) {
                    const percentage = Math.min(100, (stats.total_in_queue / 20) * 100);
                    this.updateProgressCircle(percentage);
                }
            })
            .catch(error => console.error('Error updating stats:', error));
    }

    static formatTime(minutes) {
        if (minutes < 1) {
            return "Less than 1 minute";
        } else if (minutes < 60) {
            return `${Math.round(minutes)} minutes`;
        } else {
            const hours = Math.floor(minutes / 60);
            const mins = Math.round(minutes % 60);
            return `${hours}h ${mins}m`;
        }
    }

    static showAlert(message, type = 'info') {
        const alert = document.createElement('div');
        alert.className = `alert alert-${type}`;
        alert.innerHTML = `
            <span class="material-icons-round">${type === 'warning' ? 'warning' : 'info'}</span>
            <span>${message}</span>
            <button class="alert-close">&times;</button>
        `;

        // Add to page
        const container = document.querySelector('.alert-container') || document.querySelector('main') || document.body;
        if (container) {
            container.insertBefore(alert, container.firstChild);

            // Add close functionality
            alert.querySelector('.alert-close').addEventListener('click', () => {
                alert.remove();
            });

            // Auto remove after 5 seconds
            setTimeout(() => {
                if (alert.parentNode) {
                    alert.remove();
                }
            }, 5000);
        }
    }

    static joinQueue(name, age, priority = false) {
        return fetch('/api/join-queue', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    name: name,
                    age: age,
                    priority: priority
                })
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    // Store in sessionStorage for immediate access
                    sessionStorage.setItem('user_token', data.token.id);
                    sessionStorage.setItem('user_name', data.token.name);

                    // Redirect to dashboard
                    if (data.redirect) {
                        window.location.href = data.redirect;
                    } else {
                        window.location.href = '/user/dashboard';
                    }
                } else {
                    this.showAlert(`Error: ${data.error}`, 'warning');
                }
                return data;
            })
            .catch(error => {
                console.error('Error:', error);
                this.showAlert('Failed to join queue. Please try again.', 'warning');
                return { success: false, error: error.message };
            });
    }

    static updateTokenStatus() {
        // Get token from sessionStorage or current page
        let tokenId = sessionStorage.getItem('user_token');
        if (!tokenId) {
            const tokenElement = document.querySelector('.token-id');
            if (tokenElement) {
                tokenId = tokenElement.textContent.trim();
            }
        }

        if (tokenId && tokenId.startsWith('T')) {
            fetch(`/api/user-token/${tokenId}`)
                .then(response => {
                    if (!response.ok) {
                        throw new Error('Token not found');
                    }
                    return response.json();
                })
                .then(token => {
                    // Update UI elements
                    document.querySelectorAll('[data-field="people_ahead"]').forEach(el => {
                        el.textContent = token.position - 1;
                    });

                    document.querySelectorAll('[data-field="estimated_wait"]').forEach(el => {
                        el.textContent = this.formatTime(token.estimated_wait);
                    });

                    document.querySelectorAll('[data-field="position"]').forEach(el => {
                        el.textContent = token.position;
                    });

                    // Show 10-minute alert (only once)
                    if (token.estimated_wait <= 10 && token.estimated_wait > 0) {
                        const alertKey = `alert_shown_${tokenId}`;
                        if (!sessionStorage.getItem(alertKey)) {
                            this.showAlert(`⚠ Your turn is in ~${Math.round(token.estimated_wait)} minutes. Please stay nearby.`, 'warning');
                            sessionStorage.setItem(alertKey, 'true');
                        }
                    }

                    // Update progress based on position
                    if (token.position) {
                        const progressBar = document.querySelector('.progress-bar');
                        if (progressBar) {
                            const maxPosition = 20; // Assuming max queue size
                            const progress = Math.min(100, ((maxPosition - token.position + 1) / maxPosition) * 100);
                            progressBar.style.width = `${progress}%`;
                        }
                    }
                })
                .catch(error => {
                    console.error('Error updating token status:', error);
                });
        }
    }

    static processAdminAction(action, tokenId) {
        return fetch(`/api/${action}-token/${tokenId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            });
    }

    static updateCounterStatus(counterId, status) {
        return fetch(`/api/update-counter/${counterId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ status: status })
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            });
    }

    // New methods for queue options
    static joinRegularQueue() {
        const nameInput = document.querySelector('[name="name"]');
        const name = nameInput ? nameInput.value : "User";
        const age = 30; // Default age for regular queue

        this.showAlert('Joining regular queue...', 'info');

        return this.joinQueue(name, age, false)
            .then(data => {
                if (data.success) {
                    this.showAlert('Successfully joined regular queue!', 'success');
                }
                return data;
            });
    }

    static joinPriorityQueue() {
        const nameInput = document.querySelector('[name="name"]');
        const name = nameInput ? nameInput.value : "User";
        const age = 65; // Default age for priority (elderly)

        if (confirm('Are you 60+ years old or need priority service?')) {
            this.showAlert('Joining priority queue...', 'info');

            return this.joinQueue(name, age, true)
                .then(data => {
                    if (data.success) {
                        this.showAlert('Successfully joined priority queue! You will receive faster service.', 'success');
                    }
                    return data;
                });
        }
        return Promise.resolve({ success: false });
    }
}

// Form validation
function validateForm(formId) {
    const form = document.getElementById(formId);
    if (!form) return true;

    const inputs = form.querySelectorAll('input[required]');
    let isValid = true;

    inputs.forEach(input => {
        if (!input.value.trim()) {
            input.classList.add('error');
            isValid = false;
        } else {
            input.classList.remove('error');
        }
    });

    // Check password match for register form
    if (formId === 'registerForm') {
        const password = form.querySelector('#password');
        const confirmPassword = form.querySelector('#confirm_password');

        if (password && confirmPassword && password.value !== confirmPassword.value) {
            confirmPassword.classList.add('error');
            QueueUI.showAlert('Passwords do not match', 'warning');
            isValid = false;
        }
    }

    return isValid;
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Auto-update queue stats every 10 seconds
    if (window.location.pathname.includes('dashboard') || window.location.pathname === '/') {
        QueueUI.updateQueueStats();
        setInterval(() => QueueUI.updateQueueStats(), 10000);
    }

    // Update token status every 10 seconds on user pages
    if (window.location.pathname.includes('dashboard') || window.location.pathname.includes('token')) {
        // Initial call to populate data immediately
        QueueUI.updateTokenStatus(); 
        // Set interval to poll for updates
        setInterval(() => QueueUI.updateTokenStatus(), 10000);
    }

    // Initialize progress circles
    const progressElements = document.querySelectorAll('.progress-circle-fill');
    progressElements.forEach(circle => {
        const percentage = parseInt(circle.dataset.percentage || '50');
        QueueUI.updateProgressCircle(percentage);
    });

    // Form submission handlers
    const joinQueueForm = document.getElementById('joinQueueForm');
    if (joinQueueForm) {
        joinQueueForm.addEventListener('submit', function(e) {
            e.preventDefault();

            const name = this.querySelector('[name="name"]').value.trim();
            const ageInput = this.querySelector('[name="age"]');
            const age = ageInput ? parseInt(ageInput.value) || 30 : 30;
            const priorityCheckbox = this.querySelector('[name="priority"]');
            const priority = priorityCheckbox ? priorityCheckbox.checked : false;

            if (!name) {
                QueueUI.showAlert('Please enter your name', 'warning');
                return;
            }

            // Show loading state
            const submitBtn = this.querySelector('button[type="submit"]');
            const originalText = submitBtn.textContent;
            submitBtn.textContent = 'Joining...';
            submitBtn.disabled = true;

            QueueUI.joinQueue(name, age, priority)
                .finally(() => {
                    // Restore button state
                    submitBtn.textContent = originalText;
                    submitBtn.disabled = false;
                });
        });
    }

    // Add click handlers for queue buttons
    const regularQueueBtn = document.getElementById('regularQueueBtn');
    const priorityQueueBtn = document.getElementById('priorityQueueBtn');

    if (regularQueueBtn) {
        regularQueueBtn.addEventListener('click', function() {
            QueueUI.joinRegularQueue();
        });
    }

    if (priorityQueueBtn) {
        priorityQueueBtn.addEventListener('click', function() {
            QueueUI.joinPriorityQueue();
        });
    }

    // Login form validation
    const loginForm = document.querySelector('form[action*="login"]');
    if (loginForm) {
        loginForm.addEventListener('submit', function(e) {
            if (!validateForm('')) {
                e.preventDefault();
            }
        });
    }

    // Register form validation
    const registerForm = document.querySelector('form[action*="register"]');
    if (registerForm) {
        registerForm.addEventListener('submit', function(e) {
            if (!validateForm('registerForm')) {
                e.preventDefault();
            }
        });
    }

    // Admin actions
    document.addEventListener('click', function(e) {
        // Process token button
        if (e.target.closest('.btn-process')) {
            e.preventDefault();
            const button = e.target.closest('.btn-process');
            const tokenId = button.dataset.token;

            if (confirm(`Process token ${tokenId}?`)) {
                QueueUI.processAdminAction('process', tokenId)
                    .then(data => {
                        if (data.success) {
                            // Remove the row
                            const row = button.closest('tr');
                            if (row) {
                                row.remove();
                            }
                            QueueUI.showAlert(`Token ${tokenId} processed successfully`, 'success');
                            QueueUI.updateQueueStats();
                        } else {
                            QueueUI.showAlert(`Failed to process token ${tokenId}`, 'warning');
                        }
                    })
                    .catch(error => {
                        console.error('Error:', error);
                        QueueUI.showAlert('Network error. Please try again.', 'warning');
                    });
            }
        }

        // Skip token button
        if (e.target.closest('.btn-skip')) {
            e.preventDefault();
            const button = e.target.closest('.btn-skip');
            const tokenId = button.dataset.token;

            if (confirm(`Skip token ${tokenId}? This will move it to the end of the queue.`)) {
                QueueUI.processAdminAction('skip', tokenId)
                    .then(data => {
                        if (data.success) {
                            QueueUI.showAlert(`Token ${tokenId} moved to end of queue`, 'warning');
                            // Refresh page to update positions
                            setTimeout(() => window.location.reload(), 1000);
                        } else {
                            QueueUI.showAlert(`Failed to skip token ${tokenId}`, 'warning');
                        }
                    })
                    .catch(error => {
                        console.error('Error:', error);
                        QueueUI.showAlert('Network error. Please try again.', 'warning');
                    });
            }
        }

        // Toggle counter status
        if (e.target.closest('.counter-toggle')) {
            e.preventDefault();
            const button = e.target.closest('.counter-toggle');
            const counterId = parseInt(button.dataset.counter);
            const currentStatus = button.dataset.status;
            const newStatus = currentStatus === 'open' ? 'closed' : 'open';

            QueueUI.updateCounterStatus(counterId, newStatus)
                .then(data => {
                    if (data.success) {
                        // Update button state
                        button.dataset.status = newStatus;
                        const badge = button.querySelector('.badge');
                        if (badge) {
                            badge.textContent = newStatus.toUpperCase();
                            badge.className = `badge ${newStatus === 'open' ? 'badge-success' : 'badge-danger'}`;
                        }

                        // Update text if present
                        const statusText = button.querySelector('.counter-status');
                        if (statusText) {
                            statusText.textContent = newStatus;
                        }

                        QueueUI.showAlert(`Counter ${counterId} is now ${newStatus}`, 'success');
                        QueueUI.updateQueueStats();
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    QueueUI.showAlert('Failed to update counter status', 'warning');
                });
        }
    });

    // Age validation for priority mode
    const ageInput = document.getElementById('age');
    if (ageInput) {
        ageInput.addEventListener('input', function() {
            const age = parseInt(this.value) || 0;
            const priorityBadge = document.getElementById('priorityBadge');
            const priorityCheckbox = document.getElementById('priority');

            if (priorityBadge) {
                if (age > 60) {
                    priorityBadge.style.display = 'inline-block';
                    priorityBadge.textContent = 'Elderly Priority';

                    // Auto-check priority for elderly
                    if (priorityCheckbox) {
                        priorityCheckbox.checked = true;
                    }
                } else {
                    priorityBadge.style.display = 'none';

                    // Uncheck if not elderly
                    if (priorityCheckbox && age <= 60) {
                        priorityCheckbox.checked = false;
                    }
                }
            }
        });
    }

    // Auto-fill demo data for testing
    if (window.location.pathname === '/' && !sessionStorage.getItem('demo_shown')) {
        setTimeout(() => {
            const nameInput = document.querySelector('[name="name"]');
            const ageInput = document.querySelector('[name="age"]');

            if (nameInput && ageInput && nameInput.value === '') {
                nameInput.value = 'Demo User';
                ageInput.value = '65';
                QueueUI.showAlert('Demo data loaded. Feel free to modify!', 'info');
                sessionStorage.setItem('demo_shown', 'true');
            }
        }, 1000);
    }

    // Queue joining functions for index.html
    if (window.location.pathname === '/') {
        // Add event listeners for queue option cards
        const regularQueueCard = document.querySelector('.card[onclick*="joinRegularQueue"]');
        const priorityQueueCard = document.querySelector('.card[onclick*="joinPriorityQueue"]');

        if (regularQueueCard) {
            regularQueueCard.addEventListener('click', function() {
                joinRegularQueue();
            });
        }

        if (priorityQueueCard) {
            priorityQueueCard.addEventListener('click', function() {
                joinPriorityQueue();
            });
        }

        // Manual form functions
        const showManualBtn = document.querySelector('button[onclick*="showManualForm"]');
        const hideManualBtn = document.querySelector('button[onclick*="hideManualForm"]');

        if (showManualBtn) {
            showManualBtn.addEventListener('click', showManualForm);
        }

        if (hideManualBtn) {
            hideManualBtn.addEventListener('click', hideManualForm);
        }
    }
});

// Queue joining functions for index.html
function joinRegularQueue() {
    const nameInput = document.querySelector('[name="name"]');
    const name = nameInput ? nameInput.value : "User";
    const age = 30; // Default age for regular queue

    QueueUI.showAlert('Joining regular queue...', 'info');

    QueueUI.joinQueue(name, age, false)
        .then(data => {
            if (data.success) {
                QueueUI.showAlert('Successfully joined regular queue! Redirecting to dashboard...', 'success');
            }
        })
        .catch(error => {
            QueueUI.showAlert('Failed to join queue. Please try again.', 'warning');
        });
}

function joinPriorityQueue() {
    if (confirm('Are you 60+ years old or require priority service due to special needs?\n\nPriority queue provides faster service for eligible individuals.')) {
        const nameInput = document.querySelector('[name="name"]');
        const name = nameInput ? nameInput.value : "User";
        const age = 65; // Default age for priority (elderly)

        QueueUI.showAlert('Joining priority queue...', 'info');

        QueueUI.joinQueue(name, age, true)
            .then(data => {
                if (data.success) {
                    QueueUI.showAlert('Successfully joined priority queue! You will receive faster service.', 'success');
                }
            })
            .catch(error => {
                QueueUI.showAlert('Failed to join priority queue. Please try again.', 'warning');
            });
    }
}

// Manual form functions
function showManualForm() {
    const manualForm = document.getElementById('manualForm');
    if (manualForm) {
        manualForm.style.display = 'block';
        // Scroll to form
        manualForm.scrollIntoView({ behavior: 'smooth' });
    }
}

function hideManualForm() {
    const manualForm = document.getElementById('manualForm');
    if (manualForm) {
        manualForm.style.display = 'none';
    }
}

// Export for module usage if needed
if (typeof module !== 'undefined' && module.exports) {
    module.exports = QueueUI;
}
# Queue System Improvements TODO

## Real-Time Updates
- [x] Add SocketIO client-side JavaScript to listen for "queue_update" events (already implemented in base.html)
- [x] Update admin dashboard to refresh queue list in real-time (handled by page reload)
- [x] Update user dashboard to show real-time position changes (handled by page reload)

## Fix "Done" Button Issues
- [x] Fix process_token method to properly handle counter freeing
- [x] Ensure counter status is updated correctly after processing
- [x] Improve error messages for better debugging

## Elderly Queue Authentication
- [x] Add age verification confirmation dialog for elderly queue
- [x] Prevent joining elderly queue if age < 60
- [x] Add proper validation and error handling

## Prevent Rejoining Logic
- [x] Modify join_queue to check for any active tokens (waiting, called, processed)
- [x] Only allow rejoining after admin explicitly marks as "done" and resets user status
- [x] Add proper error messages for rejoin attempts
- [x] Add API endpoint for admins to mark tokens as "done"
- [x] Comprehensive testing completed - all functionality working correctly

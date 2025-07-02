#!/bin/bash

# Quick Test Setup Script for Folder Endpoints
# Save this as test_folders.sh and make it executable: chmod +x test_folders.sh

# =============================================================================
# CONFIGURATION
# =============================================================================

# Set your configuration here
BASE_URL="http://localhost:8000"
AUTH_TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiJkOGE1MWY0OC04N2IzLTRhNzktOWRhYi1mOTZjNzM4MTBiZDkiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzUwMTU4OTEzLCJpYXQiOjE3NTAxNTUzMTMsImVtYWlsIjoicXVlbnRpbkBqYXlkLmFpIiwicGhvbmUiOiIiLCJhcHBfbWV0YWRhdGEiOnsicHJvdmlkZXIiOiJnb29nbGUiLCJwcm92aWRlcnMiOlsiZ29vZ2xlIl19LCJ1c2VyX21ldGFkYXRhIjp7ImF1ZCI6IjMyMTA4MjY5ODA1LTUzaWYwNTd0MGtncTBxbG1qcXIzc3Q2djEyNGNhamFtLmFwcHMuZ29vZ2xldXNlcmNvbnRlbnQuY29tIiwiZW1haWwiOiJxdWVudGluQGpheWQuYWkiLCJlbWFpbF92ZXJpZmllZCI6dHJ1ZSwiZXhwIjoxNzQ5NzE3NjQ5LCJpYXQiOjE3NDk3MTQwNDksImlzcyI6ImFjY291bnRzLmdvb2dsZS5jb20iLCJwaG9uZV92ZXJpZmllZCI6ZmFsc2UsInN1YiI6IjExNTA3MzYzNDQ1NTg0OTY5ODIwNSJ9LCJyb2xlIjoiYXV0aGVudGljYXRlZCIsImFhbCI6ImFhbDEiLCJhbXIiOlt7Im1ldGhvZCI6Im9hdXRoIiwidGltZXN0YW1wIjoxNzQ5NzE0MDQ5fV0sInNlc3Npb25faWQiOiJkMmU0MjIxYy05YzllLTQxODEtOTMyYS02NGUzMDFhYzU0MTAiLCJpc19hbm9ueW1vdXMiOmZhbHNlfQ.Xc4FO5fxj2h5HBSnW__lhapu7lbdtxWsmx-nvDiZGsk"
# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

print_header() {
    echo -e "\n${BLUE}=== $1 ===${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

check_prerequisites() {
    print_header "Checking Prerequisites"
    
    # Check if jq is installed
    if ! command -v jq &> /dev/null; then
        print_error "jq is not installed. Please install it for JSON formatting."
        echo "  On macOS: brew install jq"
        echo "  On Ubuntu: sudo apt-get install jq"
        exit 1
    fi
    
    # Check if curl is available
    if ! command -v curl &> /dev/null; then
        print_error "curl is not installed."
        exit 1
    fi
    
    # Check if AUTH_TOKEN is set
    if [ -z "$AUTH_TOKEN" ]; then
        print_error "AUTH_TOKEN is not set. Please edit this script and add your JWT token."
        exit 1
    fi
    
    print_success "All prerequisites met"
}

test_api_connectivity() {
    print_header "Testing API Connectivity"
    
    response=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/health")
    if [ "$response" = "200" ]; then
        print_success "API is accessible"
    else
        print_error "API is not accessible (HTTP $response)"
        exit 1
    fi
}

test_authentication() {
    print_header "Testing Authentication"
    
    # Test without auth (should fail)
    response=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/prompts/folders")
    if [ "$response" = "403" ]; then
        print_success "Authentication is properly enforced"
    else
        print_warning "Expected 403 without auth, got $response"
    fi
    
    # Test with auth (should succeed)
    response=$(curl -s -o /dev/null -w "%{http_code}" \
        -H "Authorization: Bearer $AUTH_TOKEN" \
        "$BASE_URL/prompts/folders")
    if [ "$response" = "200" ]; then
        print_success "Authentication with token works"
    else
        print_error "Authentication failed (HTTP $response)"
        exit 1
    fi
}

run_folder_tests() {
    print_header "Running Folder Endpoint Tests"
    
    # Test 1: Basic folder retrieval
    echo "Test 1: Basic folder retrieval"
    curl -s -X GET "$BASE_URL/prompts/folders" \
        -H "Authorization: Bearer $AUTH_TOKEN" | jq '.success' > /dev/null
    if [ $? -eq 0 ]; then
        print_success "Basic folder retrieval works"
    else
        print_error "Basic folder retrieval failed"
    fi
    
    # Test 2: User folders only
    echo "Test 2: User folders filter"
    curl -s -X GET "$BASE_URL/prompts/folders?type=user" \
        -H "Authorization: Bearer $AUTH_TOKEN" | jq '.success' > /dev/null
    if [ $? -eq 0 ]; then
        print_success "User folder filter works"
    else
        print_error "User folder filter failed"
    fi
    
    # Test 3: With subfolders
    echo "Test 3: Nested structure"
    curl -s -X GET "$BASE_URL/prompts/folders?withSubfolders=true" \
        -H "Authorization: Bearer $AUTH_TOKEN" | jq '.success' > /dev/null
    if [ $? -eq 0 ]; then
        print_success "Nested structure works"
    else
        print_error "Nested structure failed"
    fi
    
    # Test 4: With templates
    echo "Test 4: Template inclusion"
    curl -s -X GET "$BASE_URL/prompts/folders?withTemplates=true" \
        -H "Authorization: Bearer $AUTH_TOKEN" | jq '.success' > /dev/null
    if [ $? -eq 0 ]; then
        print_success "Template inclusion works"
    else
        print_error "Template inclusion failed"
    fi
    
    # Test 5: Full functionality
    echo "Test 5: Full functionality (subfolders + templates)"
    curl -s -X GET "$BASE_URL/prompts/folders?withSubfolders=true&withTemplates=true" \
        -H "Authorization: Bearer $AUTH_TOKEN" | jq '.success' > /dev/null
    if [ $? -eq 0 ]; then
        print_success "Full functionality works"
    else
        print_error "Full functionality failed"
    fi
    
    # Test 6: Invalid type
    echo "Test 6: Error handling for invalid type"
    response=$(curl -s -o /dev/null -w "%{http_code}" \
        -H "Authorization: Bearer $AUTH_TOKEN" \
        "$BASE_URL/prompts/folders?type=invalid")
    if [ "$response" = "400" ]; then
        print_success "Error handling works correctly"
    else
        print_warning "Expected 400 for invalid type, got $response"
    fi
}

test_pin_functionality() {
    print_header "Testing Pin/Unpin Functionality"
    
    # Get current pinned folders
    echo "Getting current pinned folders..."
    pinned_response=$(curl -s -X GET "$BASE_URL/prompts/folders/pinned" \
        -H "Authorization: Bearer $AUTH_TOKEN")
    
    if echo "$pinned_response" | jq '.success' > /dev/null 2>&1; then
        print_success "Get pinned folders works"
        echo "Current pinned folders: $(echo "$pinned_response" | jq -c '.data')"
    else
        print_error "Get pinned folders failed"
    fi
    
    # Test update pinned folders
    echo "Testing update pinned folders..."
    update_response=$(curl -s -X POST "$BASE_URL/prompts/folders/update-pinned" \
        -H "Authorization: Bearer $AUTH_TOKEN" \
        -H "Content-Type: application/json" \
        -d '{"folder_ids": []}')
    
    if echo "$update_response" | jq '.success' > /dev/null 2>&1; then
        print_success "Update pinned folders works"
    else
        print_error "Update pinned folders failed"
    fi
}

show_sample_responses() {
    print_header "Sample API Responses"
    
    echo "Basic folder structure:"
    curl -s -X GET "$BASE_URL/prompts/folders" \
        -H "Authorization: Bearer $AUTH_TOKEN" | jq '.'
    
    echo -e "\nWith nested structure and templates:"
    curl -s -X GET "$BASE_URL/prompts/folders?withSubfolders=true&withTemplates=true" \
        -H "Authorization: Bearer $AUTH_TOKEN" | jq '.'
}

interactive_testing() {
    print_header "Interactive Testing Mode"
    
    while true; do
        echo -e "\nChoose a test to run:"
        echo "1. Basic folder retrieval"
        echo "2. User folders only"
        echo "3. Official folders only"
        echo "4. With nested structure"
        echo "5. With templates"
        echo "6. Full functionality"
        echo "7. Get pinned folders"
        echo "8. Clear pinned folders"
        echo "9. Custom query"
        echo "0. Exit"
        
        read -p "Enter your choice: " choice
        
        case $choice in
            1)
                curl -s -X GET "$BASE_URL/prompts/folders" \
                    -H "Authorization: Bearer $AUTH_TOKEN" | jq '.'
                ;;
            2)
                curl -s -X GET "$BASE_URL/prompts/folders?type=user&withSubfolders=true&withTemplates=true" \
                    -H "Authorization: Bearer $AUTH_TOKEN" | jq '.'
                ;;
            3)
                curl -s -X GET "$BASE_URL/prompts/folders?type=official" \
                    -H "Authorization: Bearer $AUTH_TOKEN" | jq '.'
                ;;
            4)
                curl -s -X GET "$BASE_URL/prompts/folders?withSubfolders=true" \
                    -H "Authorization: Bearer $AUTH_TOKEN" | jq '.'
                ;;
            5)
                curl -s -X GET "$BASE_URL/prompts/folders?withTemplates=true" \
                    -H "Authorization: Bearer $AUTH_TOKEN" | jq '.'
                ;;
            6)
                curl -s -X GET "$BASE_URL/prompts/folders?withSubfolders=true&withTemplates=true" \
                    -H "Authorization: Bearer $AUTH_TOKEN" | jq '.'
                ;;
            7)
                curl -s -X GET "$BASE_URL/prompts/folders/pinned" \
                    -H "Authorization: Bearer $AUTH_TOKEN" | jq '.'
                ;;
            8)
                curl -s -X POST "$BASE_URL/prompts/folders/update-pinned" \
                    -H "Authorization: Bearer $AUTH_TOKEN" \
                    -H "Content-Type: application/json" \
                    -d '{"folder_ids": []}' | jq '.'
                ;;
            9)
                read -p "Enter query parameters (e.g., ?type=user&withTemplates=true): " params
                curl -s -X GET "$BASE_URL/prompts/folders$params" \
                    -H "Authorization: Bearer $AUTH_TOKEN" | jq '.'
                ;;
            0)
                echo "Goodbye!"
                exit 0
                ;;
            *)
                print_error "Invalid choice"
                ;;
        esac
        
        echo -e "\n---"
    done
}

# =============================================================================
# MAIN SCRIPT
# =============================================================================

main() {
    echo -e "${BLUE}"
    echo "╔═══════════════════════════════════════════════════════════════════════════════╗"
    echo "║                        Folder Endpoints Test Suite                           ║"
    echo "╚═══════════════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    
    # Check if AUTH_TOKEN is provided as argument
    if [ ! -z "$1" ]; then
        AUTH_TOKEN="$1"
    fi
    
    check_prerequisites
    test_api_connectivity
    test_authentication
    run_folder_tests
    test_pin_functionality
    
    print_header "Test Summary"
    print_success "All basic tests completed!"
    
    echo -e "\nWould you like to:"
    echo "1. See sample responses"
    echo "2. Enter interactive testing mode"
    echo "3. Exit"
    
    read -p "Choose an option (1-3): " option
    
    case $option in
        1)
            show_sample_responses
            ;;
        2)
            interactive_testing
            ;;
        3)
            echo "Tests completed successfully!"
            ;;
        *)
            echo "Invalid option. Exiting."
            ;;
    esac
}

# Run the script
if [ "${BASH_SOURCE[0]}" == "${0}" ]; then
    main "$@"
fi

#!/bin/bash

# Array of all available shadcn-ui components
components=(
    "accordion"
    "alert"
    "alert-dialog"
    "aspect-ratio"
    "avatar"
    "badge"
    "button"
    "calendar"
    "card"
    "carousel"
    "checkbox"
    "collapsible"
    "command"
    "context-menu"
    "dialog"
    "drawer"
    "dropdown-menu"
    "form"
    "hover-card"
    "input"
    "label"
    "menubar"
    "navigation-menu"
    "popover"
    "progress"
    "radio-group"
    "resizable"
    "scroll-area"
    "select"
    "separator"
    "sheet"
    "skeleton"
    "slider"
    "sonner"
    "switch"
    "table"
    "tabs"
    "textarea"
    "toast"
    "toggle"
    "toggle-group"
    "tooltip"
)

# Color codes for output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "Starting installation of shadcn-ui components..."
echo

# Loop through each component and install
for component in "${components[@]}"; do
    printf "Installing %s... " "$component"
    if pnpm dlx shadcn@latest add "$component" --yes > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC}\n"
    else
        echo -e "${RED}×${NC}"
        echo "Failed to install $component"
    fi
done

echo
echo "Installation complete!"
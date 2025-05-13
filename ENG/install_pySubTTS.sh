#!/bin/bash

# Show the main installer window
(
    while true; do
        sleep 1
    done
) | zenity --progress --width=600 --height=500 --title="Installer for pySubTTS by MoonDragon" \
    --text="<b>Installer for pySubTTS by MoonDragon</b>\n\nVersione: 1.0.0\n\nhttps://github.com/MoonDragon-MD/pySubTTS\n\nThe guided installation will follow including addictions and shortcuts on the menu" \
    --no-cancel --auto-close --pulsate &

INSTALLER_PID=$!

# Function to show a popup with the command to be performed
show_command_popup() {
    zenity --error --width=400 --text="Mistake: $1 not found.\nExecute the following command:\n\n<b>$2</b>"
}

# Check the addictions
if ! zenity --question --width=400 --text="Do you want to verify and install dependences?"; then
    INSTALL_DEPENDENCIES=false
else
    INSTALL_DEPENDENCIES=true
fi

if [ "$INSTALL_DEPENDENCIES" = true ]; then
    # Verifica Python3
    if ! command -v python3 &> /dev/null; then
        show_command_popup "Python3" "sudo apt-get install python3"
        kill $INSTALLER_PID
        exit 1
    fi

    # Check pip
    if ! command -v pip3 &> /dev/null; then
        show_command_popup "pip3" "sudo apt-get install python3-pip"
        kill $INSTALLER_PID
        exit 1
    fi

    # Check ffmpeg
    if ! dpkg-query -W fonts-dejavu &>/dev/null; then
        show_command_popup "fonts-dejavu" "sudo apt-get install ffmpeg"
        kill $INSTALLER_PID
        exit 1
    fi

    # Install Python dependencies 
    zenity --info --width=400 --text="Sto installando le dipendenze Python..."
    pip3 install pyttsx3 PyQt5 srt chardet pydub edge-tts
fi

# Asks the user to install pySubTTS
INSTALL_DIR=$(zenity --file-selection --directory --title="Select the installation directory for pySubTTS" --width=400)
if [ -z "$INSTALL_DIR" ]; then
    zenity --error --width=400 --text="No selected directory.\nCanceled installation."
    kill $INSTALLER_PID
    exit 1
fi

# Create desktop entry
zenity --info --width=400 --text="I am creating the connection in the Applications menu..."
cat > ~/.local/share/applications/pySubTTS.desktop << EOL
[Desktop Entry]
Name=pySubTTS
Comment=Dubbing with TTS and SRT
Exec=$INSTALL_DIR/pySubTTS/RunUbuntu.sh
Icon=$INSTALL_DIR/pySubTTS/icon.png
Terminal=false
Type=Application
Categories=Utility;Office;
EOL

# Create the installation directory if it doesn't exist
mkdir -p "$INSTALL_DIR"

# Copy the required files
zenity --info --width=400 --text="Installing the application..."
cp -r pySubTTS "$INSTALL_DIR/"

# Genera lo script RunUbuntu.sh
cat > "$INSTALL_DIR/pySubTTS/RunUbuntu.sh" << EOL
#!/bin/bash
cd $INSTALL_DIR/pySubTTS/
python3 pySubTTS.py
EOL

# Makes the script executable RunUbuntu.sh
chmod +x "$INSTALL_DIR/pySubTTS/RunUbuntu.sh"

# Closes the main installer window
kill $INSTALLER_PID

zenity --info --width=400 --text="Completed installation!"
zenity --info --width=400 --text="You can start pySubTTS from the applications menu"

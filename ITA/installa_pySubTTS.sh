#!/bin/bash

# Mostra la finestra principale dell'installatore
(
    while true; do
        sleep 1
    done
) | zenity --progress --width=600 --height=500 --title="Installatore per pySubTTS by MoonDragon" \
    --text="<b>Installatore per pySubTTS by MoonDragon</b>\n\nVersione: 1.0.0\n\nhttps://github.com/MoonDragon-MD/pySubTTS\n\nSeguirà l'installazione guidata comprese le dipendenze e scorciatoia sul menù" \
    --no-cancel --auto-close --pulsate &

INSTALLER_PID=$!

# Funzione per mostrare un popup con il comando da eseguire
show_command_popup() {
    zenity --error --width=400 --text="Errore: $1 non trovato.\nEsegui il seguente comando:\n\n<b>$2</b>"
}

# Verifica le dipendenze
if ! zenity --question --width=400 --text="Vuoi verificare e installare le dipendenze?"; then
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

    # Verifica pip
    if ! command -v pip3 &> /dev/null; then
        show_command_popup "pip3" "sudo apt-get install python3-pip"
        kill $INSTALLER_PID
        exit 1
    fi

    # Verifica ffmpeg
    if ! dpkg-query -W fonts-dejavu &>/dev/null; then
        show_command_popup "fonts-dejavu" "sudo apt-get install ffmpeg"
        kill $INSTALLER_PID
        exit 1
    fi

    # Installa le dipendenze Python
    zenity --info --width=400 --text="Sto installando le dipendenze Python..."
    pip3 install pip install pyttsx3 PyQt5 srt chardet pydub edge-tts
fi

# Chiede all'utente dove installare pySubTTS
INSTALL_DIR=$(zenity --file-selection --directory --title="Seleziona la cartella di installazione per pySubTTS" --width=400)
if [ -z "$INSTALL_DIR" ]; then
    zenity --error --width=400 --text="Nessuna cartella selezionata.\nInstallazione annullata."
    kill $INSTALLER_PID
    exit 1
fi

# Crea il desktop entry
zenity --info --width=400 --text="Sto creando il collegamento nel menu applicazioni..."
cat > ~/.local/share/applications/pySubTTS.desktop << EOL
[Desktop Entry]
Name=pySubTTS
Comment=Doppiaggio con TTS e SRT
Exec=$INSTALL_DIR/pySubTTS/AvviaUbuntu.sh
Icon=$INSTALL_DIR/pySubTTS/icon.png
Terminal=false
Type=Application
Categories=Utility;Office;
EOL

# Crea la cartella di installazione se non esiste
mkdir -p "$INSTALL_DIR"

# Copia i file necessari
zenity --info --width=400 --text="Installando l'applicazione..."
cp -r pySubTTS "$INSTALL_DIR/"

# Genera lo script AvviaUbuntu.sh
cat > "$INSTALL_DIR/pySubTTS/AvviaUbuntu.sh" << EOL
#!/bin/bash
cd $INSTALL_DIR/pySubTTS/
python3 pySubTTS.py
EOL

# Rende eseguibile lo script AvviaUbuntu.sh
chmod +x "$INSTALL_DIR/pySubTTS/AvviaUbuntu.sh"

# Chiude la finestra principale dell'installatore
kill $INSTALLER_PID

zenity --info --width=400 --text="Installazione completata!"
zenity --info --width=400 --text="Puoi avviare pySubTTS dal menu delle applicazioni"

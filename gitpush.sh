#!/bin/bash

# Script per automatizzare git add, commit e push

echo "=== Git Auto Commit & Push ==="
echo ""

# Git add di tutti i file
echo "📦 Aggiungendo tutti i file..."
git add .

# Verifica se ci sono modifiche da committare
if git diff --cached --quiet; then
    echo "❌ Nessuna modifica da committare!"
    exit 0
fi

# Richiedi il messaggio di commit
echo ""
echo "✍️  Inserisci il messaggio del commit:"
read commit_message

# Verifica che il messaggio non sia vuoto
if [ -z "$commit_message" ]; then
    echo "❌ Errore: il messaggio del commit non può essere vuoto!"
    exit 1
fi

# Esegui il commit
echo ""
echo "💾 Eseguendo commit..."
git commit -m "$commit_message"

# Esegui il push
echo ""
echo "🚀 Pushing su origin main..."
git push origin main

# Conferma completamento
echo ""
echo "✅ Commit e push completati con successo!"

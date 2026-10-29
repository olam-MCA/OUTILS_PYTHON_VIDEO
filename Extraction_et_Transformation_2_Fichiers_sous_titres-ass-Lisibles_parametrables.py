import os
import subprocess
import shutil
import sys
import tempfile
import re
import tkinter as tk
from tkinter import filedialog, messagebox

# ==============================================================================
# 🎛️ CONFIGURATION VISUELLE DES SOUS-TITRES (Modifiez les valeurs ici)
# ==============================================================================
TAILLE_POLICE  = 16      # Taille du texte à l'écran
TAILLE_CONTOUR = 1.0     # Épaisseur du contour noir autour des lettres
TAILLE_OMBRE   = 1.0     # Épaisseur de l'ombre portée (mettez 0.0 pour la couper)
# ==============================================================================

# --- ÉTAPE AUTOMATIQUE : INSTALLATION DE PYSUBS2 SI MANQUANT ---
try:
    import pysubs2
    from pysubs2 import SSAFile, SSAStyle, Color
except ImportError:
    print("📦 Extension 'pysubs2' manquante. Installation automatique en cours...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pysubs2"])
        import pysubs2
        from pysubs2 import SSAFile, SSAStyle, Color
        print("✅ Extension 'pysubs2' installée avec succès !\n")
    except Exception as e:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Échec de l'installation", 
            f"Impossible d'installer automatiquement l'extension requise 'pysubs2'.\n\nErreur : {str(e)}"
        )
        sys.exit(1)

def verifier_outils():
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Outil manquant", 
            "Le logiciel 'ffmpeg' ou 'ffprobe' est introuvable. Veuillez l'installer et l'ajouter au PATH de Windows."
        )
        return False
    return True

def trouver_piste_dialogues_fr(video_entree):
    """Analyse les pistes avec ffprobe pour cibler la piste 'FR Full' ou 'Français'."""
    try:
        import json
        cmd = ['ffprobe', '-v', 'error', '-select_streams', 's', '-show_entries', 'stream=index:stream_tags=title,language', '-of', 'json', video_entree]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        data = json.loads(result.stdout)
        
        if 'streams' in data:
            for i, stream in enumerate(data['streams']):
                title = stream.get('tags', {}).get('title', '').lower()
                lang = stream.get('tags', {}).get('language', '').lower()
                if ('fre' in lang or 'fra' in lang) and 'full' in title:
                    return f"0:s:{i}"
            
            for i, stream in enumerate(data['streams']):
                title = stream.get('tags', {}).get('title', '').lower()
                lang = stream.get('tags', {}).get('language', '').lower()
                if ('fre' in lang or 'fra' in lang) and 'forced' not in title:
                    return f"0:s:{i}"
    except Exception:
        pass
    return "0:s:1"

def modifier_sous_titres_mkv(video_entree, dossier_sortie):
    with tempfile.TemporaryDirectory() as dir_temp:
        srt_temp = os.path.join(dir_temp, "temp_extract.srt")
        
        # Correction ici : [0] permet de récupérer uniquement le nom en texte brut
        nom_base_video = os.path.splitext(os.path.basename(video_entree))[0]
        
        # Fichier 1 : Severance.[...]-TARDiS.ass
        nom_fichier_auto = f"{nom_base_video}.ass"
        ass_automatique = os.path.join(dossier_sortie, nom_fichier_auto)
        
        # Fichier 2 : Severance.[...]-TARDiS-Francais-Lisible.ass
        nom_fichier_lisible = f"{nom_base_video}-Francais-Lisible.ass"
        ass_lisible = os.path.join(dossier_sortie, nom_fichier_lisible)
        
        piste_cible = trouver_piste_dialogues_fr(video_entree)
        
        try:
            # 1. Extraction via ffmpeg
            print(f"   -> Étape 1/2 : Extraction automatique des dialogues ({piste_cible})...")
            res = subprocess.run([
                'ffmpeg', '-y', '-i', video_entree, 
                '-map', piste_cible, srt_temp
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
            if res.returncode != 0 or not os.path.exists(srt_temp) or os.path.getsize(srt_temp) == 0:
                return False, "Impossible d'extraire la piste des dialogues textuels."

            # 2. Application du style graphique personnalisé avec vos variables de configuration
            print(f"   -> Étape 2/2 : Application de la configuration (Taille: {TAILLE_POLICE}, Contour: {TAILLE_CONTOUR}, Ombre: {TAILLE_OMBRE})...")
            subs = SSAFile.load(srt_temp)
            subs.styles.clear()
            
            style_tv = SSAStyle()
            style_tv.fontname = "Arial"
            style_tv.fontsize = TAILLE_POLICE              
            style_tv.primarycolor = Color(255, 255, 255, 0) # Blanc
            style_tv.outlinecolor = Color(0, 0, 0, 0)       # Noir
            style_tv.outline = TAILLE_CONTOUR               
            style_tv.shadow = TAILLE_OMBRE                 
            
            subs.styles["Default"] = style_tv
            
            # Enregistrement des DEUX fichiers dans le dossier
            subs.save(ass_automatique, encoding="utf-8-sig")
            subs.save(ass_lisible, encoding="utf-8-sig")
            
            print(f"   ✅ Créé : {nom_fichier_auto}")
            print(f"   ✅ Créé : {nom_fichier_lisible}")
            return True, "Succès"

        except Exception as e:
            return False, f"Erreur : {str(e)}"

def traiter_dossier():
    root = tk.Tk()
    root.withdraw()

    if not verifier_outils():
        return

    print("📂 Ouverture de la fenêtre de sélection de dossier...")
    dossier_selectionne = filedialog.askdirectory(title="Sélectionnez le dossier de vos MKV")
    
    if not dossier_selectionne:
        print("❌ Sélection annulée.")
        return

    fichiers_mkv = [f for f in os.listdir(dossier_selectionne) if f.lower().endswith('.mkv')]
    
    if not fichiers_mkv:
        print("⚠ Aucun fichier .mkv trouvé.")
        messagebox.showwarning("Attention", "Aucun fichier .mkv n'a été trouvé.")
        return

    total_fichiers = len(fichiers_mkv)
    print(f"🎬 {total_fichiers} fichier(s) MKV détecté(s). Extraction et stylisation...\n")
    print("=" * 60)

    reussis = 0
    anomalies = 0

    for index, nom_fichier in enumerate(fichiers_mkv, 1):
        chemin_entree = os.path.join(dossier_selectionne, nom_fichier)
        print(f"[{index}/{total_fichiers}] Traitement de : {nom_fichier}")
        success, message = modifier_sous_titres_mkv(chemin_entree, dossier_selectionne)
        
        if success:
            reussis += 1
        else:
            print(f"   ❌ Ignoré : {message}\n")
            anomalies += 1

    print("=" * 60)
    print(f"📊 Résumé : {reussis} fichier(s) traité(s) avec succès.\n")

    messagebox.showinfo(
        "Traitement Terminé", 
        "C'est terminé !\n\n"
        "Le script a correctement généré les 2 fichiers .ass demandés directement à côté de chaque vidéo."
    )

if __name__ == "__main__":
    traiter_dossier()

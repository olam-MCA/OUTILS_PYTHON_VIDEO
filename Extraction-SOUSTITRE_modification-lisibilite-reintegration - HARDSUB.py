import os
import subprocess
import shutil
import sys
import tempfile
import tkinter as tk
from tkinter import filedialog, messagebox

# ==============================================================================
# 🎛️ CONFIGURATION VISUELLE DES SOUS-TITRES (Modifiez les valeurs ici)
# ==============================================================================
TAILLE_POLICE  = 16      # Augmentez ici (ex: 20 ou 22) si la TV est très loin
TAILLE_CONTOUR = 1.5     # Épaisseur du contour noir autour des lettres
TAILLE_OMBRE   = 1.0     # Épaisseur de l'ombre portée
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
        messagebox.showerror("Erreur", f"Extension manquante : {str(e)}")
        sys.exit(1)

def verifier_outils():
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        print("\nERREUR : FFmpeg ou FFprobe est introuvable. Ajoutez-les au PATH de Windows.")
        return False
    return True

def trouver_piste_dialogues_fr(video_entree):
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

def incruster_sous_titres(video_entree, dossier_sortie):
    with tempfile.TemporaryDirectory() as dir_temp:
        srt_temp = os.path.join(dir_temp, "temp_extract.srt")
        
        # Création d'un fichier ASS temporaire local au dossier
        ass_temp_brut = os.path.join(dossier_sortie, "temp_render.ass")
        
        # Échappement absolu pour Windows (FFmpeg demande d'inverser et doubler les slashes pour le filtre 'subtitles')
        ass_pour_filtre = ass_temp_brut.replace("\\", "/").replace(":", "\\:")
        
        nom_complet_video = os.path.basename(video_entree)
        nom_base_video, _ = os.path.splitext(nom_complet_video)
        
        video_sortie = os.path.join(dossier_sortie, f"{nom_base_video}_Incruste.mkv")
        piste_cible = trouver_piste_dialogues_fr(video_entree)
        
        try:
            # 1. Extraction de la piste d'origine
            print(f"   -> Étape 1/3 : Extraction des dialogues ({piste_cible})...")
            res = subprocess.run(['ffmpeg', '-y', '-hide_banner', '-i', video_entree, '-map', piste_cible, srt_temp], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if res.returncode != 0: 
                return False, "Échec de l'extraction des dialogues."

            # 2. Création de la feuille de style
            print(f"   -> Étape 2/3 : Création du style personnalisé (Taille: {TAILLE_POLICE})...")
            subs = SSAFile.load(srt_temp)
            subs.styles.clear()
            
            style_tv = SSAStyle()
            style_tv.fontname = "Arial"
            style_tv.fontsize = TAILLE_POLICE              
            style_tv.primarycolor = Color(255, 255, 255, 0) 
            style_tv.outlinecolor = Color(0, 0, 0, 0)       
            style_tv.outline = TAILLE_CONTOUR               
            style_tv.shadow = TAILLE_OMBRE                 
            subs.styles["Default"] = style_tv
            
            # Sauvegarde des fichiers finaux demandés
            subs.save(os.path.join(dossier_sortie, f"{nom_base_video}.ass"), encoding="utf-8-sig")
            subs.save(os.path.join(dossier_sortie, f"{nom_base_video}-Francais-Lisible.ass"), encoding="utf-8-sig")
            subs.save(ass_temp_brut, encoding="utf-8-sig")

            print(f"   ✅ Créé (Externe) : {nom_base_video}.ass")
            print(f"   ✅ Créé (Externe) : {nom_base_video}-Francais-Lisible.ass")

            # 3. Réencodage vidéo avec incrustation définitive ("Hardsub")
            print(f"   -> Étape 3/3 : Incrustation définitive dans l'image (Réencodage en cours)...")
            commande = [
                'ffmpeg', '-y', '-hide_banner',
                '-i', video_entree,
                '-vf', f"subtitles='{ass_pour_filtre}'", # Syntaxe sécurisée avec échappement des deux-points Windows
                '-c:v', 'libx264',                       
                '-crf', '20',                            
                '-preset', 'fast',                       
                '-c:a', 'copy',                          
                '-sn',                                   
                video_sortie
            ]
            
            res_remux = subprocess.run(commande, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
            if os.path.exists(ass_temp_brut): 
                os.remove(ass_temp_brut)

            if res_remux.returncode == 0 and os.path.exists(video_sortie):
                print(f"   ✅ Réussi : {os.path.basename(video_sortie)}\n")
                return True, "Succès"
            else:
                return False, f"Erreur FFmpeg : {res_remux.stderr}"

        except Exception as e:
            return False, f"Erreur : {str(e)}"

def traiter_dossier():
    if not verifier_outils(): 
        return

    print("📂 Sélection du dossier contenant vos fichiers MKV...")
    root = tk.Tk()
    root.withdraw()
    dossier_selectionne = filedialog.askdirectory(title="Sélectionnez le dossier de vos séries")
    if not dossier_selectionne: 
        print("❌ Sélection annulée.")
        return

    fichiers_mkv = [f for f in os.listdir(dossier_selectionne) if f.lower().endswith('.mkv') and not f.endswith('_Incruste.mkv')]
    if not fichiers_mkv: 
        print("⚠ Aucun fichier .mkv à traiter trouvé dans ce dossier.")
        return

    total = len(fichiers_mkv)
    print(f"🎬 {total} fichier(s) détecté(s). Lancement de l'incrustation...\n")
    print("=" * 60)

    reussis = 0
    for index, nom_fichier in enumerate(fichiers_mkv, 1):
        chemin_entree = os.path.join(dossier_selectionne, nom_fichier)
        print(f"[{index}/{total}] Incrustation de : {nom_fichier}")
        success, message = incruster_sous_titres(chemin_entree, dossier_selectionne)
        if success:
            reussis += 1
        else: 
            print(f"   ❌ Erreur : {message}\n")

    print("=" * 60)
    print(f"📊 Résumé : {reussis}/{total} fichier(s) incrusté(s) avec succès.")

if __name__ == "__main__":
    try:
        traiter_dossier()
    except Exception as err_globale:
        print(f"\n❌ CRASH DU SCRIPT : {str(err_globale)}")
    finally:
        print("\n" + "=" * 60)
        input("Fenêtre bloquée pour contrôle. Appuyez sur Entrée pour fermer...")

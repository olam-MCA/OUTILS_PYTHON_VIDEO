import os
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox

EXTENSIONS_SOUS_TITRES = (".srt", ".vtt", ".ass", ".ssa")


def selectionner_elements():
    """Sélectionne un dossier, puis une vidéo directement dans ce dossier."""
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        print("Étape 1 : sélection du dossier contenant les vidéos...")
        dossier = filedialog.askdirectory(
            title="Sélectionnez le dossier de travail", parent=root
        )
        if not dossier:
            print("Opération annulée : aucun dossier sélectionné.")
            return None, None

        print(f"Dossier sélectionné : {dossier}")
        print("\nÉtape 2 : sélection du fichier vidéo...")
        chemin_video = filedialog.askopenfilename(
            initialdir=dossier,
            title="Sélectionnez la vidéo à traiter",
            filetypes=[
                ("Fichiers vidéo", "*.mp4 *.mkv *.avi *.mov *.wmv"),
                ("Tous les fichiers", "*.*"),
            ],
            parent=root,
        )
        if not chemin_video:
            print("Opération annulée : aucune vidéo sélectionnée.")
            return None, None

        if os.path.normcase(os.path.abspath(os.path.dirname(chemin_video))) != os.path.normcase(os.path.abspath(dossier)):
            print("Erreur : la vidéo n'est pas dans le dossier choisi.")
            return None, None

        return dossier, chemin_video
    finally:
        root.destroy()


def trouver_tous_les_sous_titres(dossier, nom_video_sans_ext):
    """
    Recherche récursivement les fichiers SRT/VTT/ASS/SSA correspondant à la vidéo.
    Exemples : VIDEO-fr.vtt, VIDEO-ENG.vtt, VIDEO.fr.srt, VIDEO.srt.
    """
    trouves = []
    nom_cible = nom_video_sans_ext.casefold()

    for racine, _, fichiers in os.walk(dossier):
        for nom in fichiers:
            nom_min = nom.casefold()
            ext = next((e for e in EXTENSIONS_SOUS_TITRES if nom_min.endswith(e)), None)
            if not ext:
                continue

            base = nom[:-len(ext)]
            base_min = base.casefold()

            # Accepte VIDEO.srt et VIDEO-fr.vtt / VIDEO.ENG.srt / VIDEO_fr.ass.
            if base_min == nom_cible:
                trouves.append(os.path.join(racine, nom))
            elif (
                base_min.startswith(nom_cible)
                and len(base) > len(nom_video_sans_ext)
                and base[len(nom_video_sans_ext)] in ".-_ "
                and base[len(nom_video_sans_ext) + 1:].strip()
            ):
                trouves.append(os.path.join(racine, nom))

    return sorted(set(trouves), key=lambda p: (os.path.basename(p).casefold(), p.casefold()))


def langue_depuis_nom(chemin_sous_titre, nom_video_sans_ext):
    """Déduit le code de langue du suffixe du nom, si présent."""
    base = os.path.splitext(os.path.basename(chemin_sous_titre))[0]
    if base.casefold() == nom_video_sans_ext.casefold():
        return "und"  # Langue non précisée.

    suffixe = base[len(nom_video_sans_ext):].lstrip(".-_ ").strip()
    # Les noms tels que VIDEO.en-US.vtt peuvent contenir un tiret.
    # FFmpeg reçoit ce suffixe comme métadonnée; on le conserve en minuscules.
    return suffixe.lower() if suffixe else "und"


def confirmer_remplacement(fichier_sortie):
    if not os.path.exists(fichier_sortie):
        return True

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        return messagebox.askyesno(
            "Fichier déjà existant",
            "Fichier déjà existant. Veux-tu le remplacer ?",
            parent=root,
        )
    finally:
        root.destroy()


def fusionner_video_et_sous_titres():
    dossier, chemin_video = selectionner_elements()
    if not dossier or not chemin_video:
        return

    nom_fichier = os.path.basename(chemin_video)
    nom_sans_ext = os.path.splitext(nom_fichier)[0]
    fichier_sortie = os.path.join(dossier, f"{nom_sans_ext}_sous_titres.mkv")

    print("\n--- Informations sur la vidéo ---")
    print(f"Vidéo : {nom_fichier}")
    print(f"Dossier : {dossier}")

    chemins_sous_titres = trouver_tous_les_sous_titres(dossier, nom_sans_ext)
    # Sécurité : exclure le fichier de sortie si une ancienne sortie correspond au motif.
    chemins_sous_titres = [
        p for p in chemins_sous_titres
        if os.path.normcase(os.path.abspath(p)) != os.path.normcase(os.path.abspath(fichier_sortie))
    ]

    if not chemins_sous_titres:
        print("\nERREUR : aucun fichier de sous-titres correspondant trouvé.")
        print("Extensions recherchées : SRT, VTT, ASS, SSA.")
        print("Recherche effectuée dans le dossier sélectionné et ses sous-dossiers.")
        return

    print(f"\nSous-titres trouvés : {len(chemins_sous_titres)}")
    for i, chemin in enumerate(chemins_sous_titres, start=1):
        print(f"  {i}. {os.path.relpath(chemin, dossier)}")

    if os.path.normcase(os.path.abspath(fichier_sortie)) == os.path.normcase(os.path.abspath(chemin_video)):
        print("ERREUR : le fichier de sortie est la vidéo source.")
        return

    if not confirmer_remplacement(fichier_sortie):
        print("\nOpération annulée : le fichier existant a été conservé.")
        return

    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("\nERREUR : FFmpeg est introuvable.")
        print("Installe FFmpeg ou ajoute son dossier bin au PATH.")
        return

    print("\nFusion en cours...")
    print("Vidéo : copie sans réencodage.")
    print("Audio : conservation de toutes les pistes.")
    print(f"Sous-titres : ajout de {len(chemins_sous_titres)} piste(s).")

    commande = ["ffmpeg", "-hide_banner", "-i", chemin_video]
    for chemin in chemins_sous_titres:
        commande.extend(["-i", chemin])

    # Conserver la vidéo et toutes les pistes audio de la vidéo d'origine.
    commande.extend(["-map", "0:v:0?", "-map", "0:a?"])

    # Ajouter une piste par fichier de sous-titres.
    for index in range(1, len(chemins_sous_titres) + 1):
        commande.extend(["-map", f"{index}:0"])

    commande.extend(["-c:v", "copy", "-c:a", "copy", "-c:s", "srt"])

    for index, chemin in enumerate(chemins_sous_titres):
        langue = langue_depuis_nom(chemin, nom_sans_ext)
        titre = os.path.basename(chemin)
        commande.extend([
            f"-metadata:s:s:{index}", f"language={langue}",
            f"-metadata:s:s:{index}", f"title={titre}",
            f"-disposition:s:{index}", "default" if index == 0 else "0",
        ])

    # -y autorise l'écrasement seulement après la confirmation ci-dessus.
    commande.extend(["-y", fichier_sortie])

    try:
        resultat = subprocess.run(
            commande, capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
        if resultat.returncode == 0:
            print("\nSUCCÈS : fusion terminée.")
            print(f"Fichier créé :\n{fichier_sortie}")
            print(f"{len(chemins_sous_titres)} piste(s) de sous-titres ajoutée(s).")
            print("La première piste de sous-titres est déclarée par défaut.")
            print("La vidéo et l'audio n'ont pas été réencodés.")
        else:
            print("\nERREUR pendant la fusion FFmpeg :")
            print(resultat.stderr)
    except Exception as e:
        print("\nERREUR inattendue :")
        print(str(e))


if __name__ == "__main__":
    try:
        fusionner_video_et_sous_titres()
    except KeyboardInterrupt:
        print("\nOpération interrompue.")
    finally:
        print("\n" + "=" * 50)
        input("Appuyez sur Entrée pour fermer cette fenêtre...")

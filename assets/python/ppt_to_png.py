import sys
import json
from pathlib import Path
import win32com.client

def convert_ppt_to_png(ppt_file, output_dir):
    """Convert PowerPoint file to PNG slides."""
    # Initialize objects in case of early failure
    presentation = None
    powerpoint = None
    
    # Validate ppt_file exists
    if not Path(ppt_file).exists():
        print(json.dumps({
            "success": False,
            "pptFile": ppt_file,
            "outputDir": output_dir,
            "error": f"PPT file not found: {ppt_file}"
        }))
        sys.exit(1)
    
    try:
        # Create output directory
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        # Open PowerPoint application using visible window (as in test_ppt_to_png.py)
        powerpoint = win32com.client.Dispatch("PowerPoint.Application")
        powerpoint.Visible = True
        
        # Open presentation in PowerPoint
        presentation = powerpoint.Presentations.Open(
            ppt_file,
            False,
            False,
            True
        )
        
        slide_count = presentation.Slides.Count
        
        # Use SaveAs to export all slides as PNGs (Type=18)
        presentation.SaveAs(output_dir, 18)

        # Rename exported files SlideN.PNG to SlideNNN.png
        output_path = Path(output_dir)
        renamed_files = []
        for slide_num in range(1, slide_count + 1):
            src = output_path / f"Slide{slide_num}.PNG"
            dst = output_path / f"Slide{slide_num:03d}.png"
            if src.exists():
                src.rename(dst)
                renamed_files.append(dst)
            else:
                # Also check lowercase extension as fallback (just in case)
                src_lower = output_path / f"Slide{slide_num}.png"
                if src_lower.exists():
                    src_lower.rename(dst)
                    renamed_files.append(dst)

        # Gather the resulting files strictly as SlideNNN.png (1-based)
        png_files = list(sorted(output_path.glob("Slide[0-9][0-9][0-9].png")))
        png_count = len(png_files)
        
        if png_count != slide_count:
            return {
                "success": False,
                "slideCount": slide_count,
                "pngCount": png_count,
                "pptFile": ppt_file,
                "outputDir": output_dir,
                "error": f"PNG count ({png_count}) does not match slide count ({slide_count})"
            }
        
        return {
            "success": True,
            "slideCount": slide_count,
            "outputDir": output_dir,
            "pptFile": ppt_file
        }
    
    except Exception as e:
        return {
            "success": False,
            "pptFile": ppt_file,
            "outputDir": output_dir,
            "error": str(e)
        }
    
    finally:
        # Safe cleanup - check if objects exist before closing
        if presentation:
            presentation.Close()
        if powerpoint:
            powerpoint.Quit()

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(json.dumps({
            "success": False,
            "error": "Usage: python ppt_to_png.py <ppt_file> <output_dir>"
        }))
        sys.exit(1)
    
    ppt_file = sys.argv[1]
    output_dir = sys.argv[2]
    
    result = convert_ppt_to_png(ppt_file, output_dir)
    print(json.dumps(result))
    sys.exit(0 if result.get("success") else 1)
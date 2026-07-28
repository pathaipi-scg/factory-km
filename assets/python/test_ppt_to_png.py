from pathlib import Path
import win32com.client

ppt_file = r"D:\KM\Vault\MortarMixing\Mixer\RawMat_Formula.pptx"
output_dir = r"D:\KM\Vault\MortarMixing\Mixer\KM_20260602_162652"

Path(output_dir).mkdir(parents=True, exist_ok=True)

powerpoint = win32com.client.Dispatch("PowerPoint.Application")

powerpoint.Visible = True

presentation = powerpoint.Presentations.Open(
    ppt_file,
    False,
    False,
    True
)

presentation.SaveAs(output_dir,18)

presentation.Close()

powerpoint.Quit()
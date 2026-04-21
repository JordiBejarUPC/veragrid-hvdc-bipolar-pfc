import os
from trunk.test_modelica_parser.modelica_parser import ModelicaXMLParser
from trunk.test_modelica_parser.template_generator import ModelicaToPythonTranspiler

XML_FOLDER = "./modelica_xml_source"
OUTPUT_FOLDER = "./library/generated_templates"

if not os.path.exists(OUTPUT_FOLDER):
    os.makedirs(OUTPUT_FOLDER)

print("---  Starting VeraGrid Transpiler ---")

for filename in os.listdir(XML_FOLDER):
    if filename.endswith(".xml"):
        name = filename[:-4]
        xml_path = os.path.join(XML_FOLDER, filename)

        print(f"\nProcessing: {name}...")

        try:
            parser = ModelicaXMLParser(xml_source=xml_path, is_file=True)
            block = parser.parse_and_build(name)
            transpiler = ModelicaToPythonTranspiler(block, parser, name)
            saved_path = transpiler.generate_python_file(output_dir=OUTPUT_FOLDER)
            print(f"  ✅ Generated: {saved_path}")
        except Exception as e:
            print(f"  ❌ Error processing {name}: {e}")

print("\n--- Transpilation Complete ---")
from codeontology.__main__ import main


command = r"""
python3 local C:\Users\sandr\codeontology\download\Sphinx-5.2.3
--pkgs C:\Users\sandr\codeontology\download\install\project
--deps C:\Users\sandr\codeontology\download\install\dependencies
--py-src C:\Users\sandr\codeontology\download\python-source-3.9.7
"""
command_list = command.replace("\n", " ").strip().split()

main(command_list)

MAKEFLAGS+="-j 2"

.PHONY: dev

run_win:
	.\.env\Scripts\activate && uvicorn main:app --reload --host 0.0.0.0 --port 5000

run_linux:
	source .env/bin/activate && uvicorn main:app --reload --host 0.0.0.0 --port 5000
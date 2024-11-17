import typer
from datetime import datetime

app = typer.Typer()

@app.command()
def main(print_message: str = typer.Option("Hello now is: ", "--print", help="Something to print")) -> None:
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    typer.echo(f"{print_message} {timestamp} thats timestamp!")

if __name__ == "__main__":
    app()

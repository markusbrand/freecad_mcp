from src.freecad_bridge import mcp

def main():
    """Entry point for the freecad-mcp package"""
    mcp.run(transport='stdio')

if __name__ == "__main__":
    main()

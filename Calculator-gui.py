
import tkinter as tk

# Main window
root = tk.Tk()
root.title("Python Calculator")
root.geometry("350x480")
root.resizable(False, False)
root.configure(bg="#202124")

# Display variable
expression = ""

# Display screen
display = tk.Entry(
    root,
    font=("Arial", 25),
    bg="#303134",
    fg="white",
    bd=0,
    justify="right"
)
display.grid(row=0, column=0, columnspan=4,
             padx=10, pady=20, ipady=15, sticky="nsew")


# Button click function
def button_click(value):
    global expression

    if value == "C":
        expression = ""

    elif value == "DEL":
        expression = expression[:-1]

    elif value == "=":
        try:
            expression = str(eval(expression))
        except:
            expression = "Error"

    else:
        if expression == "Error":
            expression = ""
        expression += str(value)

    display.delete(0, tk.END)
    display.insert(0, expression)


# Button configuration
buttons = [
    ("C", 1, 0), ("DEL", 1, 1), ("%", 1, 2), ("/", 1, 3),
    ("7", 2, 0), ("8", 2, 1), ("9", 2, 2), ("*", 2, 3),
    ("4", 3, 0), ("5", 3, 1), ("6", 3, 2), ("-", 3, 3),
    ("1", 4, 0), ("2", 4, 1), ("3", 4, 2), ("+", 4, 3),
    ("0", 5, 0), (".", 5, 1), ("=", 5, 2)
]


# Create buttons using grid system
for text, row, col in buttons:

    if text == "=":
        color = "#34A853"
    elif text in ["+", "-", "*", "/", "%"]:
        color = "#F9AB00"
    elif text in ["C", "DEL"]:
        color = "#EA4335"
    else:
        color = "#3C4043"

    button = tk.Button(
        root,
        text=text,
        font=("Arial", 16, "bold"),
        bg=color,
        fg="white",
        activebackground="#5F6368",
        activeforeground="white",
        bd=0,
        command=lambda value=text: button_click(value)
    )

    if text == "0":
        button.grid(row=row, column=col,
                    columnspan=2, padx=5, pady=5,
                    sticky="nsew")
    elif text == "=":
        button.grid(row=row, column=col,
                    columnspan=2, padx=5, pady=5,
                    sticky="nsew")
    else:
        button.grid(row=row, column=col,
                    padx=5, pady=5, sticky="nsew")


# Configure grid size
for i in range(6):
    root.grid_rowconfigure(i, weight=1)

for i in range(4):
    root.grid_columnconfigure(i, weight=1)


# Run application
root.mainloop()

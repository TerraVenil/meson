// Is it possible to avoid this line?
// using static System.Console;
// global using System;
global using System;
global using static System.Console;
global using static System.Range;

double x = 5.5;
int y = (int)x;

// Similar to print in Python
WriteLine(x);

// myBool, myBool2 = True, False
bool myBool = true, myBool2 = false;

string name = "Jesse";

string name2 = "Bob";

WriteLine(name.CompareTo(name2));

WriteLine("Hello World!");

WriteLine(name[..]);
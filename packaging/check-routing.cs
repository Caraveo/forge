using System;
internal static class CheckRouting {
    public static int Main() {
        string[,] cases = {
            {"forge a boat", "model"}, {"build a house", "model"}, {"make a dog", "model"}, {"mold a knight helmet", "model"}, {"Mold a dragon", "model"},
            {"generate a boat", "image"}, {"create a dog", "image"}, {"imagine a cat", "image"},
            {"please remove the background", "background"}, {"could you upscale it", "upscale"},
            {"can you rig it", "rig"}, {"hello", "chat"}, {"how do I rig a model?", "chat"},
            {"do not generate anything", "chat"}, {"make sure this works", "chat"},
            {"I am thinking about a forest house", "chat"}
        };
        for (int i=0; i<cases.GetLength(0); i++) {
            string actual=Intent.Mode(cases[i,0]);
            if(actual!=cases[i,1])throw new Exception(cases[i,0]+" routed to "+actual);
        }
        Console.WriteLine("Command and conversation routing passed.");
        return 0;
    }
}

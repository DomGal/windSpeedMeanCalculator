import os, sys
import shutil

import datetime
import json

import numpy as np
import pandas as pd


class Parser:
    """klasa parser prolazi kroz datoteku i parsira"""
    """ako je dostupan učitavamo iz config file-a,
    ako nije radimo po std-configu"""
    def __init__(self, filePath, outFilePath, *,
                 configPath = None):
        self._filePath = filePath
        self._outFilePath = outFilePath
        if (configPath):
            pass
        else:
            self._config = self._makeConfig(
                self._defaultParserConfig())
        self._additionalInfo = self._getDataInfo()
        self._findPositions()
        
        return None

    def parse(self):
        parsedData = []
        with open(self._filePath, "r") as dataFile:
            data = dataFile.readlines()
            for line in data[3:]:
                parsedLine = self._parseLine(line)
                parsedData.append(parsedLine)
        #self._parsedData = parsedData
        with open(self._outFilePath, "w") as writeFile:
            writeFile.write(json.dumps(parsedData, separators=(",", ":"), indent = 4))
        return None

    def _makeConfig(self, parserConfig):
        config = dict()
        for key, value in json.loads(parserConfig).items():
            try:
                config[key] = {"size": int(value)}
            except:
                raise ValueError
        return config

    def _parseLine(self, line):
        parsedLine = dict()
        for key, value in self._config.items():
            start = value["position"]
            stop = start + value["size"]
            parsedLine[key] = int(line[start:stop])
        return parsedLine

    def _defaultParserConfig(self):
        parser_config = """{"SS":2,"mm":2,"DD":2,"mj":2,"GG":2,\
        "ssbr":4,"PRS":3,"mxbr":4,"MXS":3}"""
        return parser_config

    def _getDataInfo(self):
        with open(self._filePath, "r") as dataFile:
            data = dataFile.readlines()
            # based on header and info positions
            header = data[:2]
            columns = data[2]
            dataSplitDict = {"header": [i.strip() for i in header],
                             "columnNames": columns.strip()}
            return dataSplitDict

    def _findPositions(self):
        columnNames = self._additionalInfo["columnNames"]
        missingColumns = []
        for key in self._config.keys():
            position = columnNames.find(key)
            if (position < 0):
                missingColumns.append(key)
                self._config.pop(key)
            else:
                self._config[key]["position"] = position
        assert self._config

class Analyser:
    def __init__(self, pathToInputFile, pathToOutputFile,
                 pathToRawFile, *, extension = None):
        self._pathToFile = pathToInputFile.replace("\\", "/")
        self._pathToOutputFile = pathToOutputFile.replace("\\", "/")
        self._pathToRawFile = pathToRawFile.replace("\\", "/")
        self._extension = extension

    def _toDateTime(self, df: pd.DataFrame) -> str:
        date = datetime.date(2000 + df.GG, df.mj, df.DD)
        if (df.SS == 24):
            date = date + datetime.timedelta(1)
            df.SS = 0
        dateStr = date.isoformat()
        time = datetime.time(df.SS, df.mm)
        timeStr = time.isoformat(timespec = "minutes")
        return f"{dateStr} {timeStr}"

    def _compToDeg(self, compDeg: int) -> int:
        return (90 - compDeg) % 360

    def _degToComp(self, deg: int) -> int:
        return (90 - deg) % 360

    def _setAdditionalFields(self, df: pd.DataFrame) -> pd.DataFrame:
        df.loc[:, "time"] = pd.to_datetime(df.apply(self._toDateTime, axis = 1))
        df[(df == 999)] = np.nan
        df[(df == 9999)] = np.nan
        frame = df.set_index(df.time).drop("time", axis = 1)
        frame.loc[:, "ssbr"] = frame.ssbr / 10
        frame.loc[:, "PRS_rad"] = np.radians(self._compToDeg(frame.PRS))
        frame.loc[:, "x_sp"] = np.round(np.cos(frame.PRS_rad) * frame.ssbr, 1)
        frame.loc[:, "y_sp"] = np.round(np.sin(frame.PRS_rad) * frame.ssbr, 1)
        return frame

    def _calculateMean(self, frame: pd.DataFrame) -> pd.DataFrame:
        dsFrame = np.round(frame.resample("60T").mean().loc[:, ["x_sp", "y_sp"]], 1)
        dsFrame.loc[:, "PRS"] = self._degToComp(np.degrees(np.arctan2(dsFrame.y_sp, dsFrame.x_sp))).round()
        dsFrame.loc[:, "ssbr"] = np.sqrt(dsFrame.x_sp**2 + dsFrame.y_sp**2).round(1)
        return dsFrame

    def analyse(self) -> None:
        df = pd.read_json(self._pathToFile)
        df.to_csv(self._pathToRawFile)
        frame = self._setAdditionalFields(df)
        frame = self._calculateMean(frame)
        frame.loc[:, ["PRS", "ssbr"]].to_csv(self._pathToOutputFile)
        return None



def main() -> None:
    pathToFolder = input("Enter path to folder: ").replace("\\", "/")
    rootFolder = os.path.join(pathToFolder, "..")
    tmpFolder = os.path.join(rootFolder, "tmp")
    rawFolder = os.path.join(rootFolder, "raw")
    outFolder = os.path.join(rootFolder, "izlaz")
    os.mkdir(tmpFolder)
    os.mkdir(rawFolder)
    os.mkdir(outFolder)

    for root, _, fileNames in os.walk(pathToFolder):
        fileNames.sort()
        for fileName in fileNames:
            print(f"processing {fileName} ...")
            fileNameClean = fileName.split(".")[0].strip()

            inPath = os.path.join(root, fileName)
            tmpPath = os.path.join(tmpFolder, fileNameClean + "_tmp.json")
            rawPath = os.path.join(rawFolder, fileNameClean + "_raw.csv")
            outPath = os.path.join(outFolder, fileNameClean + ".csv")

            parser = Parser(inPath, tmpPath)
            parser.parse()

            analyser = Analyser(tmpPath, outPath, rawPath)
            analyser.analyse()
    shutil.rmtree(tmpFolder, ignore_errors = True)
    print("Done.")


if __name__ == "__main__":
    main()





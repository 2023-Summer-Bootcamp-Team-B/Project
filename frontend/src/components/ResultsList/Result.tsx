/* eslint-disable no-await-in-loop */
import axios from "axios";
import { saveAs } from "file-saver";
import JSZip from "jszip";
import { observer } from "mobx-react";
import { useState, useEffect, useCallback } from "react";

import downloadBtnImg from "../../assets/images/download.svg";
import playBtnImg from "../../assets/images/play.svg";
import sketchBook from "../../assets/images/sketchbook.png";
import sunny from "../../assets/images/sun.svg";
import WebsocketStore from "../../stores/WebsocketStore";
import Button from "../UI/Button";

type ResultPropsType = {
  title: string;
  name: string;
  image: string | undefined;
  currentImageCount: number;
};

const Result = observer(
  ({ name, title, image, currentImageCount }: ResultPropsType) => {
    const { gameResult, total, currentIdx, myId, hostId, players, send } =
      WebsocketStore;
    const [hidden, setHidden] = useState(true);
    const zip = new JSZip();
    const imgUrlList = gameResult.map((result) => result.img);
    const totalImageCount = gameResult.length - 1;

    const [IsImageLeft, setIsImageLeft] = useState(false);

    useEffect(() => {
      if (currentIdx >= total) {
        setIsImageLeft(false);
      } else {
        setIsImageLeft(true);
      }
    });

    const newGameHandler = () => {
      window.location.href = "/";
    };

    const downloadHandler = async () => {
      const promises: Promise<any>[] = [];
      Object.entries(imgUrlList).forEach(([i, imgUrl]) => {
        const promise = axios({
          url: imgUrl,
          method: "GET",
          responseType: "arraybuffer",
          withCredentials: false,
        })
          .then(({ data }) => {
            const fileName = `image_${i}.png`;
            zip.file(fileName, data, { binary: true });
          })
          .catch((err) => {
            console.log(err);
          });

        promises.push(promise);
      });

      await Promise.all(promises);
      zip
        .generateAsync({ type: "blob" })
        .then((content) => saveAs(content, "images.zip"));
    };

    const showResultHandler = () => {
      const id = players[currentIdx].player_id;

      send({ event: "wantResult", data: { playerId: id } });
    };

    const ref = useCallback((node: HTMLDivElement) => {
      if (node !== null) {
        node.scrollIntoView({ behavior: "smooth" });
      }
    }, []);

    useEffect(() => {
      setTimeout(() => {
        setHidden(false);
      }, currentImageCount * 2000);
    }, [gameResult]);

    useEffect(() => {
      setHidden(true);
    }, [gameResult]);
    /*  
    console.log(`현재인덱스: ${currentIdx}`);
    console.log(`현재 사람수: ${total}`); // 지금 현재 접속한 사람들의 숫자.
    console.log(`이전 사람수: ${Pretotal}`); // 나가기전의 사람들의 숫자.
    console.log(`index: ${currentImageCount}`); // 전체 이미지에서 몇번쨰를 보여주고 있는지를 알려줌.
    console.log(`전체 이미지 카운트: ${totalImageCount}`);
    console.log(`보정치: ${modex}`);
    console.log(`이미지가 남아있음?: ${IsImageLeft}`); */

    return (
      <>
        {!hidden && (
          <div ref={ref}>
            <div className=" text-right text-lg md:text-3xl mb-4 mr-2 relative z-10">
              <span className="mr-4">{title}</span>
              <span>{name}</span>
            </div>
            <div className=" flex items-start mb-4 ">
              <div className=" flex mt-4 relative z-10 h-[35vh]">
                <img src={sunny} alt="" className=" w-[3vw] h-[5vh] ml-4 " />
                <span className="text-lg md:text-2xl ml-1 mt-2 ">태양</span>
              </div>
              <div className=" h-[39vh]">
                <img
                  src={sketchBook}
                  alt=""
                  className=" w-[28vw] h-[39vh] relative z-10 "
                />
                <img
                  src={image}
                  alt=""
                  className=" w-[23.5vw] h-[34vh] relative left-[2.3vw] bottom-[35vh]"
                />
              </div>
            </div>
            {/* 마지막 결과가 아닌 경우 */}
            {IsImageLeft && currentImageCount === totalImageCount && (
              <div className=" flex items-center justify-center">
                <Button
                  type="button"
                  className="border-dashed border-2 border-black rounded-[25px] bg-[#E7F5FF] shadow-lg relative z-10"
                  onClick={downloadHandler}
                >
                  <img
                    src={downloadBtnImg}
                    alt="download button"
                    className=" w-[4vw] h-[8vh] p-2"
                  />
                </Button>

                {/* 내가 방장이되 이미지가 남아있고 플레이어 수가 변경되지 않았다면 다음결과 보기. */}
                {myId === hostId && IsImageLeft && (
                  <Button type="button" onClick={showResultHandler}>
                    <div className=" border-dashed border-2 border-black rounded-[25px] w-fit h-[8vh] pl-2 pr-2 ml-2 text-center bg-[#E7F5FF] shadow-lg flex justify-center items-center relative z-10">
                      <img
                        src={playBtnImg}
                        alt="play a new game"
                        className="w-[3vw] h-auto"
                      />
                      <span className="mr-2 text-xs md:text-sm lg:text-xl xl:text-2xl 2xl:text-3xl">
                        다음 결과 보기
                      </span>
                    </div>
                  </Button>
                )}

                {/* 혼자 남았는데. */}
                {myId === hostId && !IsImageLeft && (
                  <div className=" flex items-center justify-center">
                    <Button
                      type="button"
                      className="border-dashed border-2 border-black rounded-[25px] bg-[#E7F5FF] shadow-lg relative z-10"
                      onClick={downloadHandler}
                    >
                      <img
                        src={downloadBtnImg}
                        alt="download button"
                        className=" w-[4vw] h-[8vh] p-2"
                      />
                    </Button>
                    <Button type="button" onClick={newGameHandler}>
                      <div className=" border-dashed border-2 border-black rounded-[25px] w-fit h-[8vh] p-4 ml-2 text-center bg-[#E7F5FF] shadow-lg flex justify-center items-center relative z-10">
                        <img
                          src={playBtnImg}
                          alt="play a new game"
                          className="w-[3vw] h-auto"
                        />
                        <span className="mr-2 text-xs md:text-sm lg:text-xl xl:text-2xl 2xl:text-3xl">
                          새로운 턴
                        </span>
                      </div>
                    </Button>
                  </div>
                )}
              </div>
            )}
            {/* 마지막 결과인 경우 */}
            {!IsImageLeft && currentImageCount === totalImageCount && (
              <div className=" flex items-center justify-center">
                <Button
                  type="button"
                  className="border-dashed border-2 border-black rounded-[25px] bg-[#E7F5FF] shadow-lg relative z-10"
                  onClick={downloadHandler}
                >
                  <img
                    src={downloadBtnImg}
                    alt="download button"
                    className=" w-[4vw] h-[8vh] p-2"
                  />
                </Button>
                <Button type="button" onClick={newGameHandler}>
                  <div className=" border-dashed border-2 border-black rounded-[25px] w-fit h-[8vh] p-4 ml-2 text-center bg-[#E7F5FF] shadow-lg flex justify-center items-center relative z-10">
                    <img
                      src={playBtnImg}
                      alt="play a new game"
                      className="w-[3vw] h-auto"
                    />
                    <span className="mr-2 text-xs md:text-sm lg:text-xl xl:text-2xl 2xl:text-3xl">
                      새로운 턴
                    </span>
                  </div>
                </Button>
              </div>
            )}
          </div>
        )}
        <br />
      </>
    );
  }
);

export default Result;
